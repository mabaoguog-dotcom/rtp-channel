from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import bot
import github_poller as poll


def bet(now=2000000000, identity="casino:123"):
    return {"id": identity, "game": {"kind": "slots", "slug": "sweet-bonanza-2500",
            "name": "Sweet Bonanza 2500", "provider": {"slug": "pragmatic-play"}},
            "casino": {"name": "Test & Casino"}, "amount_usd": 100,
            "payout_usd": 20000, "multiplier": 200,
            "ts": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "player": {"name": "DO_NOT_PUBLISH"}}


def rtp_row():
    return {"game": bet()["game"], "rtp": 1.1, "official_rtp": .965,
            "n": 5000, "ci_low": .9, "ci_high": 1.3, "enough_sample": True}


class PollTests(unittest.TestCase):
    def test_hourly_keeps_only_most_active_verified_game(self):
        first = rtp_row()
        second = copy.deepcopy(first)
        slug, record = next((s, r) for s, r in bot.ZH_NAMES.items() if s != first["game"]["slug"])
        second["game"].update(slug=slug, name=record["en"])
        second["n"] = 1
        second["rtp"] = 99
        stamp = datetime.now(timezone.utc)
        text = "\n".join(bot.make_hourly_messages([(w, [second, first], stamp) for w in ("10m", "1h", "24h")], {}))
        self.assertIn(first["game"]["name"], text)
        self.assertNotIn(second["game"]["name"], text)

    @patch("bot.urlopen")
    def test_photo_upload_preserves_image_and_chinese_caption(self, request):
        from io import BytesIO
        request.return_value = BytesIO(b'{"ok":true,"result":{"message_id":7}}')
        jpeg = b"\xff\xd8test-image\xff\xd9"
        result = bot.telegram("123:test", "sendPhoto", {"chat_id": "@test", "photo": jpeg, "caption": "大额派彩"})
        self.assertEqual(result["message_id"], 7)
        req = request.call_args.args[0]
        self.assertIn("multipart/form-data; boundary=", req.get_header("Content-type"))
        self.assertIn(jpeg, req.data)
        self.assertIn("大额派彩".encode(), req.data)
        request.assert_called_once()

    def test_unknown_chinese_name_is_excluded_from_big_win(self):
        b = bet()
        b["game"].update(slug="unknown-game", name="Unknown Game")
        self.assertFalse(poll.eligible(b, 2000000000))
        b["game"].update(slug="sweet-bonanza-2500", name="Sweet Bonanza 1000")
        self.assertFalse(poll.eligible(b, 2000000000))

    def test_unverified_games_never_appear_in_rtp_messages(self):
        known = rtp_row()
        unknown = copy.deepcopy(known)
        unknown["game"].update(slug="unknown-game", name="Unknown Game")
        unknown["n"] = 1000000
        stamp = datetime.now(timezone.utc)
        snapshots = [(w, [unknown, known], stamp) for w in ("10m", "1h", "24h")]
        for make in (bot.make_hourly_messages, bot.make_messages):
            text = "\n".join(make(snapshots, {"top_n": 3}))
            self.assertIn("甜入心扉 2500", text)
            self.assertNotIn("Unknown Game", text)
            self.assertNotIn("中文名待核实", text)
            empty = [(w, [unknown], stamp) for w in ("10m", "1h", "24h")]
            self.assertEqual([], make(empty, {"top_n": 3}))

    def test_old_non_slot_loss_small_and_nonfinite_are_excluded(self):
        self.assertTrue(poll.eligible(bet(), 2000000000))
        self.assertFalse(poll.eligible(bet(), 2000003601))
        for key, value in [("amount_usd", 30000), ("payout_usd", 9999),
                           ("multiplier", float("nan")), ("id", "")]:
            b = bet()
            b[key] = value
            self.assertFalse(poll.eligible(b, 2000000000))
        b = bet()
        b["game"]["kind"] = "originals"
        self.assertFalse(poll.eligible(b, 2000000000))

    @patch("bot.request_json")
    def test_payout_sorted_pages_do_not_stop_at_old_timestamp(self, request):
        old, new = bet(1999997000, "old"), bet(1999999990, "new")
        request.side_effect = [{"bets": [old], "next": "cursor-two"}, {"bets": [new], "next": None}]
        rows, complete = poll.fetch_bets(2000000000, 1999999700)
        self.assertTrue(complete)
        self.assertEqual([row["id"] for row in rows], ["new"])
        self.assertIn("cursor=cursor-two", request.call_args.args[0])

    @patch("bot.request_json")
    def test_page_cap_and_duplicate_cursor(self, request):
        request.return_value = {"bets": [bet()], "next": "next"}
        _, complete = poll.fetch_bets(2000000000, 1999999700, max_pages=1)
        self.assertFalse(complete)
        with self.assertRaises(bot.BotError):
            poll.fetch_bets(2000000000, 1999999700)

    def test_dedup_cooldown_and_rolling_cap(self):
        state = poll.blank_state(2000000000)
        self.assertTrue(poll.claim_bet(state, bet(), 2000000000))
        self.assertFalse(poll.claim_bet(state, bet(), 2000000001))
        b = bet(identity="casino:456")
        self.assertFalse(poll.claim_bet(state, b, 2000000001))
        self.assertTrue(poll.claim_bet(state, b, 2000000601, cap=2))
        b["id"] = "casino:789"
        b["game"]["slug"] = "different-game"
        self.assertFalse(poll.claim_bet(state, b, 2000000602, cap=2))
        self.assertTrue(poll.claim_bet(state, b, 2000003700, cap=2))

    def test_message_is_not_called_realtime_and_has_no_player(self):
        text = poll.big_win_message(bet(), 2000000010)
        self.assertIn("定时检查", text)
        self.assertNotIn("实时", text.split("\n实时RTP查询机器人：", 1)[0])
        self.assertIn('实时RTP查询机器人：<a href="https://t.me/RTPZSBOT">@RTPZSBOT</a>', text)
        self.assertNotIn("DO_NOT_PUBLISH", text)
        self.assertIn("甜入心扉 2500", text)
        self.assertIn("$19,900.00", text)

    @patch("github_poller.time.sleep")
    @patch("bot.check_channel", return_value=-100123)
    @patch("bot.telegram", return_value={"message_id": 1})
    @patch("github_poller.fetch_bets", return_value=([], True))
    @patch("bot.get_rows", return_value=[rtp_row()])
    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "123:test"})
    def test_hourly_is_sent_once_across_poll_runs(self, rows, fetch, telegram, channel, sleep):
        class Store:
            def __init__(self): self.state = poll.blank_state(2000000000)
            def load(self, now): return copy.deepcopy(self.state)
            def save(self, state): self.state = copy.deepcopy(state)
        store = Store()
        poll.run(store, {"fetch_limit": 200}, send=True, now=2000000000)
        poll.run(store, {"fetch_limit": 200}, send=True, now=2000000001)
        self.assertEqual(telegram.call_count, 1)
        poll.run(store, {"fetch_limit": 200}, send=True, now=2000003600)
        self.assertEqual(telegram.call_count, 2)

    @patch("github_poller.time.time", return_value=2000000000)
    @patch("github_poller.time.sleep")
    @patch("bot.check_channel", return_value=-100123)
    @patch("bot.telegram", return_value={"message_id": 1})
    @patch("github_poller.fetch_bets", return_value=([bet()], True))
    @patch("bot.get_rows", side_effect=bot.BotError("RTP unavailable"))
    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "123:test"})
    def test_rtp_failure_does_not_block_big_win_or_post_error_notice(self, rows, fetch, telegram, channel, sleep, clock):
        class Store:
            def __init__(self): self.state = poll.blank_state(2000000000)
            def load(self, now): return copy.deepcopy(self.state)
            def save(self, state): self.state = copy.deepcopy(state)
        store = Store()
        poll.run(store, {"fetch_limit": 200}, send=True, now=2000000000)
        self.assertIsNone(store.state["hourly_slot"])
        self.assertEqual(telegram.call_count, 1)
        self.assertEqual("sendPhoto", telegram.call_args.args[1])
        self.assertIn("大额派彩记录", telegram.call_args.args[2]["caption"])
        self.assertTrue(telegram.call_args.args[2]["photo"].startswith(b"\xff\xd8"))

    @patch("github_poller.time.time", return_value=2000000000)
    @patch("github_poller.time.sleep")
    @patch("bot.check_channel", return_value=-100123)
    @patch("bot.telegram", side_effect=bot.BotError("uncertain send"))
    @patch("github_poller.fetch_bets", return_value=([bet()], True))
    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "123:test"})
    def test_checkpoint_before_send_and_failed_send_not_repeated(self, fetch, telegram, channel, sleep, clock):
        class MemoryStore:
            def __init__(self):
                self.state = poll.blank_state(2000000000)
                self.state["hourly_slot"] = int(2000000000 // 3600)
                self.saves = []
            def load(self, now):
                return copy.deepcopy(self.state)
            def save(self, state):
                self.state = copy.deepcopy(state)
                self.saves.append(copy.deepcopy(state))
        store = MemoryStore()
        config = {"fetch_limit": 200}
        poll.run(store, config, send=True, now=2000000000)
        self.assertEqual(store.saves[0]["events"]["casino:123"]["status"], "reserved")
        self.assertEqual(telegram.call_count, 1)
        poll.run(store, config, send=True, now=2000000000)
        self.assertEqual(telegram.call_count, 1)

    @patch("github_poller.time.time", return_value=2000000000)
    @patch("bot.check_channel", return_value=-100123)
    @patch("bot.telegram")
    @patch("github_poller.fetch_bets", return_value=([bet()], True))
    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "123:test"})
    def test_state_push_failure_prevents_telegram_send(self, fetch, telegram, channel, clock):
        class BrokenStore:
            def load(self, now):
                s = poll.blank_state(now)
                s["hourly_slot"] = int(now // 3600)
                return s
            def save(self, state):
                raise bot.BotError("push failed")
        with self.assertRaises(bot.BotError):
            poll.run(BrokenStore(), {}, send=True, now=2000000000)
        telegram.assert_not_called()

    @patch("github_poller.fetch_bets", return_value=([bet()], True))
    @patch("bot.get_rows", return_value=[])
    @patch("bot.telegram")
    def test_preview_does_not_persist_or_send(self, telegram, rows, fetch):
        class PreviewStore:
            def load(self, now): return poll.blank_state(now)
            def save(self, state): raise AssertionError("preview must not save")
        with tempfile.TemporaryDirectory() as directory:
            original = Path.cwd()
            try:
                import os
                os.chdir(directory)
                poll.run(PreviewStore(), {"fetch_limit": 200}, now=2000000000)
            finally:
                os.chdir(original)
        telegram.assert_not_called()

    def test_remote_state_persists_without_touching_source_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, clone = root / "remote.git", root / "source"
            def git(*args, cwd=None):
                return subprocess.run(["git", *args], cwd=cwd, check=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
            git("init", "--bare", str(remote))
            git("init", "-b", "main", str(clone))
            git("remote", "add", "origin", str(remote), cwd=clone)
            (clone / "source.txt").write_text("source code remains unchanged")
            git("add", "source.txt", cwd=clone)
            git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "source", cwd=clone)
            head = git("rev-parse", "HEAD", cwd=clone)
            class LocalGitStore(poll.StateStore):
                def git(self, *args, **kwargs):
                    return super().git("-C", str(clone), *args, **kwargs)
            store = LocalGitStore(str(root / "local-state.json"), github=True)
            state = store.load(2000000000)
            poll.claim_bet(state, bet(), 2000000000)
            store.save(state)
            store2 = LocalGitStore(str(root / "another-state.json"), github=True)
            restored = store2.load(2000000001)
            self.assertIn("casino:123", restored["events"])
            restored["last_check"] = 2000000001
            store2.save(restored)
            self.assertEqual(head, git("rev-parse", "HEAD", cwd=clone))
            self.assertEqual((clone / "source.txt").read_text(), "source code remains unchanged")
            self.assertEqual(json.loads(git("show", "rtp-bot-state:state.json", cwd=remote))["last_check"], 2000000001)


if __name__ == "__main__":
    unittest.main()
