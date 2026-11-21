"""GitHub-only scheduled big-win checks and hourly RTP. Standard library only."""
import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode

import bot
from game_poster import prepare_poster, prepare_hourly_poster

STATE_REF = "refs/heads/rtp-bot-state"


def timestamp(bet):
    try:
        stamp = datetime.fromisoformat(bet["ts"].replace("Z", "+00:00"))
        return stamp.timestamp() if stamp.tzinfo else None
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def eligible(bet, now, minimum=100):
    if not isinstance(bet, dict) or not isinstance(bet.get("game"), dict):
        return False
    game = bet["game"]
    if game.get("kind") != "slots" or not re.fullmatch(r"[a-z0-9-]+", game.get("slug", "")):
        return False
    if not bot.chinese_name(game):
        return False
    if not isinstance(bet.get("id"), str) or not 1 <= len(bet["id"]) <= 256:
        return False
    if not all(bot.number(bet.get(k)) and bet[k] >= 0
               for k in ("amount_usd", "payout_usd", "multiplier")):
        return False
    stamp = timestamp(bet)
    return (stamp is not None and -30 <= now - stamp <= 3600 and
            bet["multiplier"] >= minimum and bet["payout_usd"] > bet["amount_usd"])


def fetch_bets(now, last_check, max_pages=50):
    # big-wins is NOT time-sorted: never stop at an old event inside a page.
    window = "10m" if now - last_check <= 480 else "1h"
    cutoff = max(now - 3600, last_check - 120)
    cursor, cursors, found = None, set(), {}
    for _ in range(max_pages):
        params = {"feed": "lucky", "window": window, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        key = os.environ.get("GAMBATRACKER_API_KEY", "").strip()
        data = bot.request_json(f"{bot.BASE}/api/bets?{urlencode(params)}",
                                headers={"x-api-key": key} if key else {})
        if not isinstance(data, dict) or not isinstance(data.get("bets"), list):
            raise bot.BotError("大额记录接口结构发生变化")
        for bet in data["bets"]:
            if not isinstance(bet, dict):
                raise bot.BotError("大额记录格式无效")
            stamp = timestamp(bet)
            if stamp is not None and stamp >= cutoff and isinstance(bet.get("id"), str):
                found[bet["id"]] = bet
        cursor = data.get("next")
        if not cursor:
            return list(found.values()), True
        if not isinstance(cursor, str) or cursor in cursors:
            raise bot.BotError("数据源分页游标无效或重复")
        cursors.add(cursor)
    # Do not advance the watermark if the bounded scan is incomplete.
    print("扫描达到页数上限；本次仅处理已读记录，保留上次检查时间；不向频道发异常通知")
    return list(found.values()), False


def blank_state(now):
    return {"version": 1, "last_check": now - 480, "hourly_slot": None, "events": {}}


def validate_state(state):
    if (not isinstance(state, dict) or state.get("version") != 1 or
            not bot.number(state.get("last_check")) or
            not isinstance(state.get("events"), dict) or
            (state.get("hourly_slot") is not None and not isinstance(state["hourly_slot"], int))):
        raise bot.BotError("去重状态无效；已停止发送以避免重复")
    for value in state["events"].values():
        if (not isinstance(value, dict) or not bot.number(value.get("claimed")) or
                not isinstance(value.get("game"), str)):
            raise bot.BotError("去重记录无效；已停止发送")
    return state


class StateStore:
    def __init__(self, path="preview/poller-state.json", github=False):
        self.path, self.github, self.parent = Path(path), github, None

    def git(self, *args, data=None, allowed=(0,)):
        env = dict(os.environ, GIT_AUTHOR_NAME="rtp-channel",
                   GIT_AUTHOR_EMAIL="rtp-channel@users.noreply.github.com",
                   GIT_COMMITTER_NAME="rtp-channel",
                   GIT_COMMITTER_EMAIL="rtp-channel@users.noreply.github.com")
        result = subprocess.run(["git", *args], input=data, text=True, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        if result.returncode not in allowed:
            raise bot.BotError("GitHub 去重状态读写失败；未继续发送，请检查 contents: write 权限和分支规则")
        return result

    def load(self, now):
        if self.github:
            remote = self.git("ls-remote", "--exit-code", "--heads", "origin", STATE_REF, allowed=(0, 2))
            if remote.returncode == 2:
                return blank_state(now)
            self.git("fetch", "--no-tags", "--depth=1", "origin", STATE_REF)
            self.parent = self.git("rev-parse", "FETCH_HEAD").stdout.strip()
            raw = self.git("show", f"{self.parent}:state.json").stdout
        elif self.path.exists():
            raw = self.path.read_text()
        else:
            return blank_state(now)
        try:
            return validate_state(json.loads(raw))
        except (ValueError, TypeError):
            raise bot.BotError("去重状态不是有效JSON；已停止发送") from None

    def save(self, state):
        raw = json.dumps(validate_state(state), ensure_ascii=False, sort_keys=True)
        if self.github:
            blob = self.git("hash-object", "-w", "--stdin", data=raw).stdout.strip()
            tree = self.git("mktree", data=f"100644 blob {blob}\tstate.json\n").stdout.strip()
            args = ["commit-tree", tree]
            if self.parent:
                args += ["-p", self.parent]
            commit = self.git(*args, data="Save RTP notification state\n").stdout.strip()
            # Fast-forward only; never force-push or edit source branches.
            self.git("push", "origin", f"{commit}:{STATE_REF}")
            self.parent = commit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(raw, encoding="utf-8")
        temporary.replace(self.path)


def claim_bet(state, bet, now, cap=6, cooldown=600):
    state["events"] = {key: value for key, value in state["events"].items()
                       if value["claimed"] >= now - 7 * 86400}
    if bet["id"] in state["events"]:
        return False
    recent = [value for value in state["events"].values() if value["claimed"] > now - 3600]
    if len(recent) >= cap or any(value["game"] == bet["game"]["slug"] and
                                value["claimed"] > now - cooldown for value in recent):
        return False
    state["events"][bet["id"]] = {"game": bet["game"]["slug"], "claimed": now, "status": "reserved"}
    return True


def big_win_message(bet, checked):
    casino = html.escape(str((bet.get("casino") or {}).get("name", "未知赌场"))[:80])
    stamp = datetime.fromtimestamp(timestamp(bet), timezone.utc)
    checked_at = datetime.fromtimestamp(checked, timezone.utc)
    return ("<b>🏆 大倍数记录 · 定时检查</b>\n\n" + bot.game_title(bet["game"]) +
            f"\n赌场：{casino}\n投注：${bet['amount_usd']:,.2f}\n"
            f"派彩：${bet['payout_usd']:,.2f}\n"
            f"本笔净赢：${bet['payout_usd'] - bet['amount_usd']:,.2f}\n"
            f"倍数：{bet['multiplier']:,.2f}x\n"
            f"事件：{bot.beijing_time(stamp)} 北京时间\n"
            f"检查：{bot.beijing_time(checked_at)} 北京时间\n\n"
            "历史观测记录，不预测下一次结果；计划每5分钟检查，可能延迟。\n"
            '实时RTP查询机器人：<a href="https://t.me/RTPZSBOT">@RTPZSBOT</a>')


def send_messages(messages, token, channel_id):
    for index, message in enumerate(messages):
        if bot.utf16len(message) >= 4096:
            raise bot.BotError("消息过长，已停止发送")
        if index:
            time.sleep(1.1)
        bot.telegram(token, "sendMessage", {
            "chat_id": channel_id, "text": message, "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True}})


def big_win_caption(bet, checked):
    record = bot.chinese_name(bet["game"])
    title = html.escape(record["zh"] + "（" + str(bet["game"].get("name", ""))[:100] + "）")
    return ("<b>🏆 大倍数记录</b>\n\n" + title +
            f"\n赌场：{html.escape(str((bet.get('casino') or {}).get('name', '未知赌场'))[:60])}"
            f"\n投注：${bet['amount_usd']:,.2f}\n派彩：${bet['payout_usd']:,.2f}"
            f"\n本笔净赢：${bet['payout_usd'] - bet['amount_usd']:,.2f}"
            f"\n倍数：{bet['multiplier']:,.2f}x"
            f"\n事件：{bot.beijing_time(datetime.fromtimestamp(timestamp(bet), timezone.utc))} 北京时间"
            f"\n检查：{bot.beijing_time(datetime.fromtimestamp(checked, timezone.utc))} 北京时间"
            "\n\n历史观测记录，不预测下一次结果。"
            '\n实时RTP查询机器人：<a href="https://t.me/RTPZSBOT">@RTPZSBOT</a>')


def send_big_win(bet, checked, token, channel_id):
    caption = big_win_caption(bet, checked)
    if bot.utf16len(caption) > 1000:
        raise bot.BotError("图片说明过长，未发送")
    poster = prepare_poster(bet)
    bot.telegram(token, "sendPhoto", {"chat_id": channel_id, "photo": poster,
                                      "caption": caption, "parse_mode": "HTML"})


def run(store, config, send=False, now=None):
    now = time.time() if now is None else now
    state = store.load(now)
    minimum = float(os.environ.get("BIG_WIN_MIN_MULTIPLIER", "100"))
    if not bot.number(minimum) or minimum <= 0:
        raise bot.BotError("赢奖倍数门槛无效")
    try:
        bets, complete = fetch_bets(now, state["last_check"])
    except bot.BotError as exc:
        bets, complete = [], False
        print(f"大额接口读取失败：{exc}；本次跳过，不向频道发异常通知")
    candidates = sorted((b for b in bets if eligible(b, now, minimum)),
                        key=lambda b: (b["multiplier"], timestamp(b)), reverse=True)
    due = state["hourly_slot"] is None or int(now // 3600) > state["hourly_slot"]
    hourly = []
    if due or not send:
        try:
            snapshots = [(window, bot.get_rows(window, config["fetch_limit"]), datetime.now(timezone.utc))
                         for window in ("10m", "1h", "24h")]
            hourly = bot.make_hourly_messages(snapshots, config)
        except bot.BotError:
            print("RTP读取失败，本次跳过，下一次检查可重试；不向频道发异常通知")
    preview = Path("preview")
    preview.mkdir(exist_ok=True)
    hourly_poster = prepare_hourly_poster(snapshots, config) if hourly else None
    if hourly_poster:
        (preview / "hourly-1.jpg").write_bytes(hourly_poster)
    for index, message in enumerate(hourly, 1):
        (preview / f"hourly-{index}.html").write_text(message, encoding="utf-8")
    if not send:
        count = 0
        for bet in candidates:
            if claim_bet(state, bet, now):
                count += 1
                (preview / f"big-win-{count}.html").write_text(big_win_caption(bet, now), encoding="utf-8")
                (preview / f"big-win-{count}.jpg").write_bytes(prepare_poster(bet))
        print(f"仅预览：{len(hourly)}条RTP汇总、{count}条大额记录；没有发送、没有写入GitHub去重状态")
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise bot.BotError("请配置 TELEGRAM_BOT_TOKEN Secret")
    channel_id = bot.check_channel(token, config)
    if due and hourly:
        state["hourly_slot"] = int(now // 3600)
        store.save(state)  # Remote checkpoint BEFORE Telegram, including uncertain outcomes.
        try:
            caption = hourly[0]
            if bot.utf16len(html.unescape(re.sub(r"<[^>]+>", "", caption))) > 1024:
                raise bot.BotError("每小时图片说明过长")
            if hourly_poster:
                bot.telegram(token, "sendPhoto", {"chat_id": channel_id, "photo": hourly_poster,
                                                   "caption": caption, "parse_mode": "HTML"})
            else:
                send_messages(hourly, token, channel_id)
        except bot.BotError:
            print("RTP发送失败或结果未知，已占位避免重发；不发异常通知")
    for bet in candidates:
        # Recheck after fetching/pushing; never post records older than the window.
        current = time.time()
        if not eligible(bet, current, minimum) or not claim_bet(state, bet, current):
            continue
        store.save(state)
        try:
            send_big_win(bet, now, token, channel_id)
            state["events"][bet["id"]]["status"] = "sent"
            print("已推送1条大额记录")
        except bot.BotError:
            state["events"][bet["id"]]["status"] = "unknown_or_failed"
            print("大额记录发送失败或结果未知，不重试、不发异常通知")
        store.save(state)
        time.sleep(1.1)
    if complete:
        state["last_check"] = now
    store.save(state)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--github", action="store_true", help="persist state in a separate GitHub branch")
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    bot.validate_config(config)
    config["channel"] = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or config["channel"]
    run(StateStore(github=args.github), config, send=args.send)


if __name__ == "__main__":
    try:
        main()
    except (bot.BotError, ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc) if isinstance(exc, bot.BotError) else f"运行失败：{type(exc).__name__}；不向频道发异常通知", file=sys.stderr)
        sys.exit(1)
