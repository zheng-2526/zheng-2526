from copy import deepcopy
import json
import unittest
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

from engine import (InvalidMove, after, initial, in_check, legal_moves,
                    other, parse_move, play, position_key, pseudo, request)
from render import board_svg, issue_link, section, update_readme, START, END
from bot import generated, handle


def position(pieces, turn='red'):
    s = initial()
    s['board'] = [['' for _ in range(9)] for _ in range(10)]
    for square, piece in pieces.items():
        x, y, _, _ = parse_move(square + square)
        s['board'][y][x] = piece
    s['turn'] = turn
    s['positions'] = [position_key(s)]
    return s


class Rules(unittest.TestCase):
    def test_initial_44_legal_moves_and_1920_replies(self):
        s = initial()
        moves = legal_moves(s)
        self.assertEqual(len(moves), 44)
        replies = 0
        for move in moves:
            child = deepcopy(s)
            child['board'] = after(s['board'], *parse_move(move))
            child['turn'] = other(s['turn'])
            replies += len(legal_moves(child))
        self.assertEqual(replies, 1920)

    def test_horse_leg(self):
        b = position({'e9': 'K', 'd0': 'k', 'b7': 'H', 'b6': 'P'})['board']
        self.assertFalse(pseudo(b, 1, 7, 2, 5))
        self.assertTrue(pseudo(b, 1, 7, 3, 6))

    def test_elephant_eye_and_river(self):
        b = position({'c5': 'E', 'd6': 'P'})['board']
        self.assertFalse(pseudo(b, 2, 5, 4, 7))
        self.assertFalse(pseudo(b, 2, 5, 0, 3))
        self.assertTrue(pseudo(b, 2, 5, 0, 7))

    def test_cannon_screen_capture_and_empty_move(self):
        b = position({'b7': 'C', 'b3': 'p', 'b0': 'r'})['board']
        self.assertTrue(pseudo(b, 1, 7, 1, 0))
        self.assertFalse(pseudo(b, 1, 7, 1, 3))
        self.assertFalse(pseudo(b, 1, 7, 1, 2))
        self.assertTrue(pseudo(b, 1, 7, 1, 4))
        b[2][1] = 'p'
        self.assertFalse(pseudo(b, 1, 7, 1, 0))

    def test_rook_blockers(self):
        b = initial()['board']
        self.assertFalse(pseudo(b, 0, 9, 0, 5))
        self.assertFalse(pseudo(b, 0, 9, 1, 8))
        self.assertTrue(pseudo(b, 0, 9, 0, 7))

    def test_palace(self):
        b = position({'d9': 'K', 'd8': 'A'})['board']
        self.assertFalse(pseudo(b, 3, 9, 2, 9))
        self.assertFalse(pseudo(b, 3, 8, 2, 7))
        self.assertTrue(pseudo(b, 3, 8, 4, 7))

    def test_red_and_black_pawns(self):
        b = position({'a6': 'P', 'c4': 'P', 'e3': 'p', 'g5': 'p'})['board']
        self.assertTrue(pseudo(b, 0, 6, 0, 5))
        self.assertFalse(pseudo(b, 0, 6, 1, 6))
        self.assertTrue(pseudo(b, 2, 4, 3, 4))
        self.assertFalse(pseudo(b, 2, 4, 2, 5))
        self.assertTrue(pseudo(b, 4, 3, 4, 4))
        self.assertFalse(pseudo(b, 4, 3, 5, 3))
        self.assertTrue(pseudo(b, 6, 5, 5, 5))
        self.assertFalse(pseudo(b, 6, 5, 6, 4))

    def test_flying_generals_and_pin(self):
        s = position({'e9': 'K', 'e0': 'k', 'e5': 'R'})
        self.assertFalse(in_check(s['board'], 'red'))
        self.assertNotIn('e5d5', legal_moves(s))
        self.assertIn('e5e4', legal_moves(s))
        self.assertNotIn('e5e0', legal_moves(s))
        s['board'][5][4] = ''
        self.assertTrue(in_check(s['board'], 'red'))
        self.assertTrue(in_check(s['board'], 'black'))

    def test_cannot_ignore_check(self):
        s = position({'e9': 'K', 'd0': 'k', 'e5': 'r', 'a6': 'P'})
        self.assertTrue(in_check(s['board'], 'red'))
        self.assertNotIn('a6a5', legal_moves(s))
        self.assertNotIn('e9d9', legal_moves(s))  # Would face the black general.
        self.assertIn('e9f9', legal_moves(s))

    def test_stalemate_is_loss(self):
        s = position({'e9': 'K', 'e0': 'k', 'e5': 'p', 'd8': 'r', 'f7': 'r'}, 'black')
        result = play(s, 'f7f8', 'visitor', 1, 'now')
        self.assertEqual((result['status'], result['winner'], result['reason']), ('won', 'black', '困毙'))

    def test_checkmate(self):
        s = position({'e9': 'K', 'e0': 'k', 'e5': 'p', 'd8': 'r', 'f8': 'r', 'e7': 'r'}, 'black')
        result = play(s, 'e7e8', 'visitor', 1, 'now')
        self.assertEqual((result['status'], result['winner'], result['reason']), ('won', 'black', '将死'))
        self.assertEqual(legal_moves(result), [])

    def test_threefold_repetition(self):
        s = initial()
        for i, move in enumerate(['b9c7', 'b0c2', 'c7b9', 'c2b0'] * 2):
            s = play(s, move, 'visitor', i+1, 'now')
        self.assertEqual(s['status'], 'draw')
        self.assertIn('三次', s['reason'])

    def test_quiet_draw_and_capture_reset(self):
        s = initial()
        s['quiet'] = 119
        self.assertEqual(play(s, 'a6a5', 'visitor', 1, 'now')['status'], 'draw')
        result = play(s, 'b7b0', 'visitor', 1, 'now')
        self.assertEqual(result['quiet'], 0)
        self.assertEqual(result['history'][-1]['captured'], 'h')
        self.assertEqual(result['status'], 'playing')

    def test_move_is_immutable_and_records_actor(self):
        s = initial()
        snapshot = deepcopy(s)
        result = play(s, 'a6a5', 'guest-1', 42, 'now')
        self.assertEqual(s, snapshot)
        self.assertEqual(result['turn'], 'black')
        self.assertEqual(result['history'][0]['actor'], 'guest-1')
        self.assertEqual(result['processed_issues'], [42])


class Requests(unittest.TestCase):
    def test_stale_and_wrong_game_rejected(self):
        s = play(initial(), 'a6a5', 'a', 1, 'now')
        for title in ['xq|move|1|0|c6c5', 'xq|move|2|1|a3a4']:
            with self.assertRaisesRegex(InvalidMove, '棋盘已更新'):
                request(s, title, 'guest', 'owner', 2, 'now')

    def test_idempotent(self):
        s, changed, _ = request(initial(), 'xq|move|1|0|a6a5', 'guest', 'owner', 42, 'now')
        again, changed, _ = request(s, 'xq|move|1|0|a6a5', 'guest', 'owner', 42, 'now')
        self.assertFalse(changed)
        self.assertIs(again, s)

    def test_only_owner_resets_active_game(self):
        with self.assertRaisesRegex(InvalidMove, '只有主页主人'):
            request(initial(), 'xq|new|1|0', 'guest', 'owner', 1, 'now')
        s, changed, _ = request(initial(), 'xq|new|1|0', 'OWNER', 'owner', 1, 'now')
        self.assertEqual((s['game'], s['ply'], changed), (2, 0, True))

    def test_anyone_can_start_after_end(self):
        s = initial()
        s['status'] = 'draw'
        new, _, _ = request(s, 'xq|new|1|0', 'guest', 'owner', 1, 'now')
        self.assertEqual(new['game'], 2)
        self.assertEqual(len(legal_moves(new)), 44)

    def test_invalid_titles_and_finished_moves(self):
        for title in ['xq|new|1|0|a6a5', 'xq|move|1|0', 'xq|move|1|0|a9a0;echo bad', 'xq|move|1|0|a0z9']:
            with self.assertRaises(InvalidMove):
                request(initial(), title, 'guest', 'owner', 1, 'now')
        s = initial()
        s['status'] = 'draw'
        with self.assertRaisesRegex(InvalidMove, '结束'):
            play(s, 'a6a5', 'guest', 1, 'now')


class Presentation(unittest.TestCase):
    def test_all_move_links_parse_and_are_legal(self):
        s = initial()
        for move in legal_moves(s):
            url = issue_link('owner/owner', s, 'move', move)
            title = parse_qs(urlparse(url).query)['title'][0]
            _, changed, _ = request(s, title, 'guest', 'owner', 1, 'now')
            self.assertTrue(changed)

    def test_svg_well_formed_32_pieces_and_dynamic_status(self):
        s = initial()
        root = ET.fromstring(board_svg(s))
        ns = {'s': 'http://www.w3.org/2000/svg'}
        self.assertEqual(len(root.findall('.//s:g/s:title', ns)), 32)
        s = play(s, 'a6a5', 'guest', 1, 'now')
        svg = board_svg(s)
        ET.fromstring(svg)
        self.assertIn('黑方行棋', svg)
        self.assertIn('A6 → A5', svg)

    def test_preserve_intro_and_trailing_text(self):
        before = '# Existing profile\n\nMy personal content.\n'
        text = update_readme(before, initial(), 'owner/owner') + '\nFooter must survive.\n'
        text = update_readme(text, initial(2), 'owner/owner')
        self.assertTrue(text.startswith(before))
        self.assertTrue(text.endswith('Footer must survive.\n'))
        self.assertEqual(text.count(START), 1)
        self.assertEqual(text.count(END), 1)
        self.assertIn('第 2 局', text)

    def test_ambiguous_markers_rejected(self):
        for text in [START, END, START + END + START, END + START]:
            with self.assertRaises(ValueError):
                update_readme(text, initial(), 'owner/owner')

    def test_generated_json_svg_and_markdown_agree(self):
        s = play(initial(), 'a6a5', 'guest', 1, 'now')
        files = generated(s, '# Hi\n', 'owner/owner')
        self.assertEqual(json.loads(files['xiangqi/state.json'])['ply'], 1)
        self.assertIn('黑方行棋', files['assets/xiangqi/board.svg'])
        self.assertIn('xq%7Cmove%7C1%7C1', files['README.md'])
        self.assertIn('@guest', files['README.md'])


class FakeGitHub:
    repo = 'owner/owner'

    def __init__(self, state=None, title='xq|move|1|0|a6a5', actor='guest'):
        self.state = state or initial()
        self.readme = '# Hi\n'
        self.current = dict(number=42, state='open', title=title, user=dict(login=actor, type='User'))
        self.replies, self.commits = [], []

    def api(self, path, method='GET', data=None):
        if path == '/issues/42' and method == 'GET':
            return self.current
        raise AssertionError((path, method))

    def snapshot(self):
        return ('main', 'sha', 'tree', self.readme, self.state)

    def commit(self, snapshot, files, message):
        self.state = json.loads(files['xiangqi/state.json'])
        self.readme = files['README.md']
        self.commits.append(files)

    def answer(self, number, text):
        self.replies.append(text)
        self.current['state'] = 'closed'


class Controller(unittest.TestCase):
    def test_accept_commit_reply_and_close(self):
        gh = FakeGitHub()
        handle(gh, {'number': 42})
        self.assertEqual(gh.state['ply'], 1)
        self.assertEqual(len(gh.commits), 1)
        self.assertEqual(gh.current['state'], 'closed')
        self.assertIn('✅', gh.replies[0])

    def test_stale_issue_does_not_change_board(self):
        gh = FakeGitHub(state=play(initial(), 'a6a5', 'first', 1, 'now'))
        handle(gh, {'number': 42})
        self.assertEqual(gh.state['ply'], 1)
        self.assertFalse(gh.commits)
        self.assertIn('棋盘已更新', gh.replies[0])

    def test_reset_archives_previous_game(self):
        gh = FakeGitHub(title='xq|new|1|0', actor='owner')
        handle(gh, {'number': 42})
        self.assertEqual(gh.state['game'], 2)
        archived = json.loads(gh.commits[0]['xiangqi/games/game-000001.json'])
        self.assertEqual(archived['status'], 'aborted')

    def test_unrelated_issues_are_untouched(self):
        gh = FakeGitHub(title='Hello, nice profile')
        handle(gh, {'number': 42})
        self.assertFalse(gh.commits or gh.replies)
        self.assertEqual(gh.current['state'], 'open')


if __name__ == '__main__':
    unittest.main()
