"""Dependency-free Xiangqi rules. Coordinates: a0 at black's upper-left."""
from copy import deepcopy
import re

NAMES = dict(zip('KAEHRCPkaehrcp', '帥仕相馬車炮兵將士象馬車砲卒'))
SIDES = {'red': '红方', 'black': '黑方'}


class InvalidMove(ValueError):
    pass


def side(piece):
    return ('red' if piece.isupper() else 'black') if piece else None


def other(color):
    return 'black' if color == 'red' else 'red'


def initial(game=1):
    rows = ['rheakaehr', '.........', '.c.....c.', 'p.p.p.p.p', '.........',
            '.........', 'P.P.P.P.P', '.C.....C.', '.........', 'RHEAKAEHR']
    board = [[p if p != '.' else '' for p in row] for row in rows]
    state = dict(schema=1, game=game, ply=0, turn='red', board=board,
                 status='playing', winner=None, reason='', quiet=0, history=[],
                 positions=[], processed_issues=[], last_move=None)
    state['positions'] = [position_key(state)]
    return state


def position_key(state):
    return '/'.join(''.join(p or '.' for p in row) for row in state['board']) + ':' + state['turn']


def coord(x, y):
    return chr(97 + x) + str(y)


def parse_move(move):
    if not re.fullmatch(r'[a-i][0-9][a-i][0-9]', move):
        raise InvalidMove('坐标格式应为 a6a5，例如 A6 → A5。')
    return ord(move[0]) - 97, int(move[1]), ord(move[2]) - 97, int(move[3])


def palace(x, y, color):
    return 3 <= x <= 5 and (7 <= y <= 9 if color == 'red' else 0 <= y <= 2)


def pseudo(board, sx, sy, tx, ty):
    """Movement/attack geometry only; self-check is handled separately."""
    if not (0 <= sx < 9 and 0 <= tx < 9 and 0 <= sy < 10 and 0 <= ty < 10):
        return False
    piece, target = board[sy][sx], board[ty][tx]
    if not piece or (sx == tx and sy == ty) or side(piece) == side(target):
        return False
    color, kind = side(piece), piece.upper()
    dx, dy = tx - sx, ty - sy
    ax, ay = abs(dx), abs(dy)
    if kind in ('R', 'C', 'K') and (dx == 0 or dy == 0):
        stepx = (dx > 0) - (dx < 0)
        stepy = (dy > 0) - (dy < 0)
        x, y, blockers = sx + stepx, sy + stepy, 0
        while (x, y) != (tx, ty):
            blockers += bool(board[y][x])
            x, y = x + stepx, y + stepy
        if kind == 'R':
            return blockers == 0
        if kind == 'C':
            return blockers == (1 if target else 0)
        if dx == 0 and target.upper() == 'K' and blockers == 0:
            return True  # Flying generals are attacks, never a playable king capture.
    if kind == 'K':
        return ax + ay == 1 and palace(tx, ty, color)
    if kind == 'A':
        return ax == ay == 1 and palace(tx, ty, color)
    if kind == 'E':
        return (ax == ay == 2 and not board[sy + dy // 2][sx + dx // 2]
                and (ty >= 5 if color == 'red' else ty <= 4))
    if kind == 'H':
        if (ax, ay) not in ((1, 2), (2, 1)):
            return False
        lx, ly = (sx + dx // 2, sy) if ax == 2 else (sx, sy + dy // 2)
        return not board[ly][lx]
    if kind == 'P':
        forward = -1 if color == 'red' else 1
        crossed = sy <= 4 if color == 'red' else sy >= 5
        return (dx == 0 and dy == forward) or (crossed and ay == 0 and ax == 1)
    return False


def in_check(board, color):
    king = 'K' if color == 'red' else 'k'
    found = next(((x, y) for y in range(10) for x in range(9) if board[y][x] == king), None)
    if found is None:
        return True
    return any(side(board[y][x]) == other(color) and pseudo(board, x, y, *found)
               for y in range(10) for x in range(9))


def after(board, sx, sy, tx, ty):
    result = [row[:] for row in board]
    result[ty][tx], result[sy][sx] = result[sy][sx], ''
    return result


def legal_moves(state):
    if state['status'] != 'playing':
        return []
    board, color = state['board'], state['turn']
    moves = []
    for sy in range(10):
        for sx in range(9):
            if side(board[sy][sx]) != color:
                continue
            for ty in range(10):
                for tx in range(9):
                    if (board[ty][tx].upper() != 'K' and pseudo(board, sx, sy, tx, ty)
                            and not in_check(after(board, sx, sy, tx, ty), color)):
                        moves.append(coord(sx, sy) + coord(tx, ty))
    return moves


def play(state, move, actor, issue, at):
    parse_move(move)
    if state['status'] != 'playing':
        raise InvalidMove('本局已结束，请先开启新局。')
    if move not in legal_moves(state):
        raise InvalidMove('这一步不合法：请检查棋子走法、轮次，以及是否解除将军。')
    result = deepcopy(state)
    sx, sy, tx, ty = parse_move(move)
    piece, captured = state['board'][sy][sx], state['board'][ty][tx]
    result['board'] = after(state['board'], sx, sy, tx, ty)
    result['turn'] = other(state['turn'])
    result['ply'] += 1
    result['quiet'] = 0 if captured else result['quiet'] + 1
    entry = dict(ply=result['ply'], move=move, actor=actor, issue=issue, at=at,
                 piece=piece, captured=captured, check=in_check(result['board'], result['turn']))
    result['history'].append(entry)
    result['last_move'] = move
    result['processed_issues'].append(issue)
    key = position_key(result)
    result['positions'].append(key)
    if not legal_moves(result):
        result.update(status='won', winner=state['turn'], reason='将死' if entry['check'] else '困毙')
    elif result['positions'].count(key) >= 3:
        result.update(status='draw', reason='同一局面三次出现（社区简化和棋规则）')
    elif result['quiet'] >= 120:
        result.update(status='draw', reason='连续 60 回合未吃子（社区简化和棋规则）')
    return result


def request(state, title, actor, owner, issue, at):
    """Validate revision and authorize resets before producing a new state."""
    if issue in state['processed_issues']:
        return state, False, '这条请求已经处理过，无需重复操作。'
    match = re.fullmatch(r'xq\|(move|new)\|([1-9][0-9]{0,8})\|([0-9]{1,8})(?:\|([a-i][0-9][a-i][0-9]))?', title)
    if not match:
        raise InvalidMove('请求格式不正确，请从主页的走法链接重新进入。')
    action, game, ply, move = match.groups()
    if (int(game), int(ply)) != (state['game'], state['ply']):
        raise InvalidMove('棋盘已更新！已有其他访客先走一步，请刷新主页后重新选择。')
    if action == 'move':
        if move is None:
            raise InvalidMove('缺少走法。')
        result = play(state, move, actor, issue, at)
        return result, True, f'已落子：{move[:2].upper()} → {move[2:].upper()}。'
    if move is not None:
        raise InvalidMove('新局请求不应包含走法。')
    if state['status'] == 'playing' and actor.lower() != owner.lower():
        raise InvalidMove('本局仍在进行，只有主页主人可以提前重开；对局结束后任何人都能开新局。')
    result = initial(state['game'] + 1)
    result['processed_issues'] = [issue]
    return result, True, '新局已开启，红方先行！'
