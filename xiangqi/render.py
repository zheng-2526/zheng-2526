"""Generate a self-contained SVG and a Markdown move selector."""
from collections import Counter, defaultdict
from html import escape
from urllib.parse import urlencode
from engine import NAMES, SIDES, in_check, legal_moves, parse_move, side

START = '<!-- XIANGQI:START -->'
END = '<!-- XIANGQI:END -->'


def status_text(state):
    if state['status'] == 'won':
        return f"{SIDES[state['winner']]}获胜 · {state['reason']}"
    if state['status'] == 'draw':
        return '本局和棋'
    return SIDES[state['turn']] + ('行棋 · 将军！' if in_check(state['board'], state['turn']) else '行棋')


def board_svg(state):
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="1150" viewBox="0 0 960 1150" role="img" aria-labelledby="title desc">',
           '<title id="title">接力中国象棋</title>',
           f'<desc id="desc">第 {state["game"]} 局，第 {state["ply"]} 手，{status_text(state)}。黑方在上，红方在下；列 A 到 I，行 0 到 9。请在图片下方的合法走法表中落子。</desc>',
           '<defs><linearGradient id="paper" x2="1" y2="1"><stop stop-color="#faf6ec"/><stop offset="1" stop-color="#eee4cf"/></linearGradient>',
           '<radialGradient id="piece"><stop stop-color="#fffdf5"/><stop offset=".8" stop-color="#f4e6c8"/><stop offset="1" stop-color="#dac293"/></radialGradient></defs>',
           '<rect width="960" height="1150" rx="24" fill="url(#paper)"/>',
           '<g font-family="Microsoft YaHei,PingFang SC,Noto Sans CJK SC,sans-serif">',
           '<text x="70" y="47" font-size="12" font-weight="700" letter-spacing="4" fill="#6f7c70">YAZE / COMMUNITY XIANGQI</text>',
           '<text x="66" y="106" font-family="STKaiti,KaiTi,serif" font-size="44" font-weight="700" fill="#263c35">接力中国象棋</text>',
           '<text x="70" y="144" font-size="16" fill="#68746b">一人一步，众人成局。下一手，交给你。</text>',
           '<rect x="686" y="70" width="204" height="47" rx="23" fill="#263c35"/>',
           f'<text x="788" y="100" text-anchor="middle" font-size="18" fill="#fcf5e4">{escape(status_text(state))}</text>',
           f'<text x="884" y="144" text-anchor="end" font-size="14" fill="#68746b">第 {state["game"]:02d} 局 / 已走 {state["ply"]} 手</text>',
           '<rect x="102" y="185" width="756" height="832" rx="12" fill="#f0dfbc" stroke="#d0b98b"/>',
           '<rect x="147" y="225" width="666" height="746" fill="none" stroke="#806d49" stroke-width="3"/>',
           '<g stroke="#96815b" stroke-width="1.4" fill="none">']
    for y in range(10):
        out.append(f'<path d="M160 {238+y*80}H800"/>')
    for x in range(9):
        xx = 160 + x * 80
        out.append(f'<path d="M{xx} 238V558 M{xx} 638V958"/>')
    out += ['<path d="M160 558V638 M800 558V638 M400 238L560 398 M560 238L400 398 M400 798L560 958 M560 798L400 958"/>', '</g>',
            '<g font-family="STKaiti,KaiTi,serif" font-size="31" fill="#8d744b" text-anchor="middle"><text x="320" y="609" letter-spacing="12">楚河</text><text x="640" y="609" letter-spacing="12">漢界</text></g>']
    for x in range(9):
        for yy in (200, 1008):
            out.append(f'<text x="{160+x*80}" y="{yy}" text-anchor="middle" font-size="13" fill="#766a52">{chr(65+x)}</text>')
    for y in range(10):
        for xx in (124, 836):
            out.append(f'<text x="{xx}" y="{243+y*80}" text-anchor="middle" font-size="13" fill="#766a52">{y}</text>')
    last = parse_move(state['last_move']) if state['last_move'] else None
    if last:
        sx, sy, tx, ty = last
        out.append(f'<circle cx="{160+sx*80}" cy="{238+sy*80}" r="12" fill="#c4984d" opacity=".6"/>')
        out.append(f'<circle cx="{160+tx*80}" cy="{238+ty*80}" r="38" fill="#be9349" opacity=".4"/>')
    for y, row in enumerate(state['board']):
        for x, p in enumerate(row):
            if not p:
                continue
            xx, yy = 160 + x*80, 238 + y*80
            color = '#ad3036' if side(p) == 'red' else '#293c38'
            out += [f'<g><title>{SIDES[side(p)]}{NAMES[p]} {chr(65+x)}{y}</title>',
                    f'<circle cx="{xx}" cy="{yy+3}" r="32" fill="#a98a56" opacity=".35"/>',
                    f'<circle cx="{xx}" cy="{yy}" r="32" fill="url(#piece)" stroke="#c5a773" stroke-width="1.5"/>',
                    f'<circle cx="{xx}" cy="{yy}" r="26.5" fill="none" stroke="{color}" stroke-width="1.3"/>',
                    f'<text x="{xx}" y="{yy+12}" text-anchor="middle" font-family="STKaiti,KaiTi,Microsoft YaHei,serif" font-size="33" font-weight="700" fill="{color}">{NAMES[p]}</text></g>']
    out += ['<path d="M70 1050H890" stroke="#d4c7ac"/>',
            '<text x="70" y="1084" font-size="13" fill="#768074">ONE BOARD. EVERYONE PLAYS.</text>',
            '<text x="70" y="1116" font-size="15" fill="#354c40">黑方在上 · 红方在下 · 红方先行</text>']
    if state['history']:
        e = state['history'][-1]
        out.append(f'<text x="890" y="1085" text-anchor="end" font-size="14" fill="#354c40">上一手 {NAMES[e["piece"]]} {e["move"][:2].upper()} → {e["move"][2:].upper()}</text>')
        out.append(f'<text x="890" y="1116" text-anchor="end" font-size="13" fill="#768074">by @{escape(e["actor"])}</text>')
    else:
        out.append('<text x="890" y="1116" text-anchor="end" font-size="15" fill="#354c40">欢迎走出第一手 →</text>')
    out.append('</g></svg>\n')
    return '\n'.join(out)


def issue_link(repo, state, action, move=None):
    title = f'xq|{action}|{state["game"]}|{state["ply"]}' + ('|' + move if move else '')
    body = ('点击 Submit new issue（提交新议题）即可完成请求，请保留标题。\n\n'
            '这是一盘所有访客共同参与的中国象棋。请求会自动检查合法性；'
            '如果别人先走了一步，请刷新主页后重新选择。\n\n'
            f'返回棋盘：https://github.com/{repo.split("/")[0]}#接力中国象棋')
    return f'https://github.com/{repo}/issues/new?' + urlencode(dict(title=title, body=body))


def section(state, repo):
    moves = legal_moves(state)
    lines = [START, '## 接力中国象棋', '',
             '**一人一步，众人成局。** 所有访客共享这盘棋，红黑轮流，欢迎接下一手。', '',
             f'**第 {state["game"]} 局 · {status_text(state)} · 已走 {state["ply"]} 手**', '',
             f'<img src="./assets/xiangqi/board.svg?game={state["game"]}&amp;ply={state["ply"]}" width="720" alt="接力中国象棋棋盘：{status_text(state)}；黑方在上，红方在下" />', '']
    if moves:
        lines += ['### 轮到你了', '',
                  '在下表找到棋子，**点击目标坐标 → 提交预填好的 Issue → 等待自动回复 → 刷新主页**。需要登录 GitHub。', '',
                  '坐标看棋盘边缘：列 **A–I** 从左到右，行 **0–9** 从上到下。下表只列出当前合法走法。', '',
                  f'<details open>\n<summary><b>{SIDES[state["turn"]]}可走的棋子 · 共 {len(moves)} 种走法</b></summary>\n',
                  '| 棋子 · 起点 | 点击选择落点 |', '| :--- | :--- |']
        groups = defaultdict(list)
        for move in moves:
            groups[move[:2]].append(move)
        for origin, group in groups.items():
            sx, sy, _, _ = parse_move(group[0])
            destinations = []
            for move in group:
                _, _, tx, ty = parse_move(move)
                target = state['board'][ty][tx]
                label = move[2:].upper() + (f'（吃{NAMES[target]}）' if target else '')
                destinations.append(f'[{label}]({issue_link(repo, state, "move", move)})')
            lines.append(f'| {NAMES[state["board"][sy][sx]]} **{origin.upper()}** | ' + ' · '.join(destinations) + ' |')
        lines += ['', '</details>', '', '> 多人同时落子时，只接受当前局面的第一步有效走法；过期请求会提示重新选择。']
    else:
        lines += [f'**本局结束：{state["reason"]}。**', '',
                  f'### [开启下一局 · 红方先行]({issue_link(repo, state, "new")})', '任何访客都可以开新局，上一局会自动归档。']
    lines += ['', '<details>\n<summary><b>最近十手 · 接力记录</b></summary>\n']
    if not state['history']:
        lines.append('棋盘已经摆好，等你走出第一手。')
    else:
        lines += ['| 手数 | 阵营 | 走法 | 接力者 |', '| :--- | :--- | :--- | :--- |']
        for e in reversed(state['history'][-10:]):
            move = e['move']
            label = f'{NAMES[e["piece"]]} {move[:2].upper()} → {move[2:].upper()}'
            if e['captured']:
                label += f' · 吃{NAMES[e["captured"]]}'
            if e['check']:
                label += ' · 将军'
            lines.append(f'| {e["ply"]} | {SIDES[side(e["piece"])]} | [{label}](https://github.com/{repo}/issues/{e["issue"]}) | [@{e["actor"]}](https://github.com/{e["actor"]}) |')
    lines += ['', '</details>', '', '<details>\n<summary><b>本局棋友与吃子</b></summary>\n']
    participants = Counter(e['actor'] for e in state['history'])
    lines.append(' · '.join(f'[@{u}](https://github.com/{u}) × {n}' for u, n in participants.most_common()) or '尚无接力者，欢迎加入。')
    for color in ('red', 'black'):
        captures = [NAMES[e['captured']] for e in state['history'] if e['captured'] and side(e['piece']) == color]
        lines.append(f'\n{SIDES[color]}吃子：' + (' '.join(captures) or '暂无'))
    lines += ['', '</details>', '', '<details>\n<summary><b>玩法与和棋约定</b></summary>\n',
              '- 红方先行，所有人均可替当前一方走一步，也可以连续参与。',
              '- 自动检查蹩马腿、塞象眼、炮架、九宫、过河、将帅照面与应将。将死和困毙均判负。',
              '- 社区简化规则：同一局面（含行棋方）第三次出现，或连续 60 回合双方未吃子，判和。长将、长捉暂不采用专业赛事裁决。',
              '- 正在进行的对局只允许主页主人提前重开；对局结束后任何人都能开新局。',
              '- 自动更新通常需要数十秒，以 Issue 中的机器人回复为准。',
              f'- [查看完整记录与项目说明](https://github.com/{repo}/tree/main/xiangqi) · [查看自动更新状态](https://github.com/{repo}/actions/workflows/xiangqi.yml)',
              '', '</details>', END]
    return '\n'.join(lines) + '\n'


def update_readme(original, state, repo):
    replacement = section(state, repo)
    if START not in original and END not in original:
        return original.rstrip() + '\n\n---\n\n' + replacement
    if original.count(START) != 1 or original.count(END) != 1 or original.index(START) > original.index(END):
        raise ValueError('README game markers are ambiguous; refusing to overwrite unrelated content')
    start, end = original.index(START), original.index(END) + len(END)
    return original[:start] + replacement.rstrip('\n') + original[end:]
