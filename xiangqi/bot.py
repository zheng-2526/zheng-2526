"""GitHub Issue controller; only trusted default-branch code is executed."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from engine import InvalidMove, initial, request
from render import board_asset, board_svg, update_readme

ROOT = Path(__file__).resolve().parents[1]
STATE = 'xiangqi/state.json'
BOARD = 'assets/xiangqi/board.svg'


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def generated(state, readme, repo):
    svg = board_svg(state)
    return {STATE: dump(state), BOARD: svg, board_asset(state, svg): svg,
            'README.md': update_readme(readme, state, repo)}


class GitHub:
    def __init__(self, repo, token):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('Invalid repository')
        self.repo = repo
        self.base = 'https://api.github.com/repos/' + repo
        self.token = token

    def api(self, path, method='GET', data=None):
        body = json.dumps(data).encode() if data is not None else None
        req = Request(self.base + path, data=body, method=method,
                      headers={'Authorization': 'Bearer ' + self.token,
                               'Accept': 'application/vnd.github+json',
                               'X-GitHub-Api-Version': '2022-11-28',
                               'Content-Type': 'application/json',
                               'User-Agent': 'community-xiangqi'})
        with urlopen(req, timeout=30) as response:
            content = response.read()
            return json.loads(content) if content else None

    def file(self, path, ref):
        result = self.api(f'/contents/{path}?ref={ref}')
        return base64.b64decode(result['content']).decode('utf-8')

    def snapshot(self):
        branch = self.api('')['default_branch']
        head = self.api(f'/git/ref/heads/{branch}')['object']['sha']
        tree = self.api(f'/git/commits/{head}')['tree']['sha']
        readme = self.file('README.md', head)
        state = json.loads(self.file(STATE, head))
        return branch, head, tree, readme, state

    def commit(self, snapshot, files, message):
        branch, head, tree, _, _ = snapshot
        entries = []
        for path, content in files.items():
            blob = self.api('/git/blobs', 'POST', {'content': content, 'encoding': 'utf-8'})
            entries.append(dict(path=path, mode='100644', type='blob', sha=blob['sha']))
        new_tree = self.api('/git/trees', 'POST', {'base_tree': tree, 'tree': entries})
        if new_tree['sha'] == tree:
            return head
        commit = self.api('/git/commits', 'POST', {
            'message': message, 'tree': new_tree['sha'], 'parents': [head]})
        # Reject a concurrent main-branch update; never force-push a game state.
        self.api(f'/git/refs/heads/{branch}', 'PATCH', {'sha': commit['sha'], 'force': False})
        return commit['sha']

    def answer(self, number, text):
        self.api(f'/issues/{number}/comments', 'POST', {'body': text})
        self.api(f'/issues/{number}', 'PATCH', {'state': 'closed'})


def handle(github, issue):
    number = issue['number']
    current = github.api(f'/issues/{number}')
    if current['state'] != 'open' or 'pull_request' in current:
        return
    title, actor = current['title'], current['user']['login']
    if not title.startswith('xq|'):
        return
    # Bots and malformed user identities do not play. No issue text enters a shell.
    if current['user']['type'] != 'User' or not re.fullmatch(r'[A-Za-z0-9-]{1,39}', actor):
        github.answer(number, '此棋局只接受已登录的个人账号参与。')
        return
    homepage = 'https://github.com/' + github.repo.split('/')[0] + '#接力中国象棋'
    for attempt in range(3):
        snapshot = github.snapshot()
        state, readme = snapshot[4], snapshot[3]
        try:
            new, changed, message = request(state, title, actor, github.repo.split('/')[0], number,
                                            datetime.now(timezone.utc).isoformat())
        except InvalidMove as exc:
            github.answer(number, f'♟️ {exc}\n\n[返回主页，刷新棋盘]({homepage})')
            return
        if changed:
            files = generated(new, readme, github.repo)
            if new['game'] != state['game']:
                archived = dict(state)
                if archived['status'] == 'playing':
                    archived.update(status='aborted', reason='主页主人提前重开')
                files[f'xiangqi/games/game-{state["game"]:06d}.json'] = dump(archived)
            try:
                github.commit(snapshot, files, f'xiangqi: game {new["game"]}, ply {new["ply"]} by @{actor} (#{number})')
            except HTTPError as exc:
                if exc.code not in (409, 422) or attempt == 2:
                    raise
                time.sleep(attempt + 1)
                continue
        github.answer(number, f'✅ {message}\n\n感谢 @{actor} 接力！[返回主页，刷新棋盘]({homepage})')
        return


def pending(github):
    """Drain open requests too, so canceled/overflowed workflow events aren't lost."""
    requests = []
    for page in range(1, 11):
        issues = github.api(f'/issues?state=open&sort=created&direction=asc&per_page=100&page={page}')
        requests.extend(i for i in issues if i['title'].startswith('xq|') and 'pull_request' not in i)
        if len(issues) < 100:
            break
    for issue in requests:
        handle(github, issue)


def local_render(repo):
    state_path = ROOT / STATE
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else initial()
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    for path, content in generated(state, readme, repo).items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')
    print(f'Rendered game {state["game"]}, ply {state["ply"]}.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    repo = os.environ.get('GITHUB_REPOSITORY', 'zheng-2526/zheng-2526')
    if args.local:
        local_render(repo)
        return
    github = GitHub(repo, os.environ['GH_TOKEN'])
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    # Process the triggering request first, and then recover any pending requests.
    if os.environ.get('GITHUB_EVENT_NAME') == 'issues':
        handle(github, event['issue'])
    pending(github)
    snapshot = github.snapshot()
    github.commit(snapshot, generated(snapshot[4], snapshot[3], repo), 'xiangqi: refresh board')
    print('Xiangqi requests processed and profile synchronized.')


if __name__ == '__main__':
    main()
