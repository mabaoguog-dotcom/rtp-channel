"""Send one explicitly requested, freshly fetched RTP snapshot."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from game_poster import prepare_hourly_poster

import bot


def main():
    config = json.load(open("config.json", encoding="utf-8"))
    snapshots = []
    for window in ("10m", "1h", "24h"):
        rows = bot.get_rows(window, config["fetch_limit"])
        if window == "24h":
            rows = sorted((r for r in rows if bot.chinese_name(r["game"])),
                          key=lambda r: r["n"], reverse=True)[:1]
        snapshots.append((window, rows, datetime.now(timezone.utc)))
    messages = bot.make_hourly_messages(snapshots, config)
    if len(messages) != 1 or bot.utf16len(messages[0]) >= 4096:
        raise bot.BotError("未生成一条有效汇总，未发送")
    message = messages[0].replace("每小时 · 活跃老虎机第1名", "即时查询 · 活跃老虎机第1名")
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    channel = bot.check_channel(token, config)
    poster = prepare_hourly_poster(snapshots, config)
    if poster is None:
        first = bot.hourly_first(snapshots, config)
        cached = Path("game-covers") / (first["game"]["slug"] + ".jpg")
        if not cached.exists():
            raise bot.BotError("对应游戏海报暂不可用，未发送")
        poster = cached.read_bytes()
    result = bot.telegram(token, "sendPhoto", {
        "chat_id": channel, "photo": poster, "caption": message, "parse_mode": "HTML"})
    print("已发送一条最新RTP汇总：https://t.me/rtpbodon/" + str(result["message_id"]))


if __name__ == "__main__":
    try:
        main()
    except bot.BotError as exc:
        raise SystemExit(str(exc)) from None
