"""GambaTracker observed slot RTP digest. Python standard library only."""
import argparse
from datetime import datetime, timedelta, timezone
import html
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE = "https://gambatracker.com"
BEIJING_TIMEZONE = timezone(timedelta(hours=8), name="北京时间")
LABELS = {"10m": "近10分钟", "1h": "近1小时", "24h": "近24小时",
          "7d": "近7天", "30d": "近30天", "all": "全部历史"}

# Published Chinese titles, manually checked against exact English editions.
# Embedded so mobile users only need to replace bot.py. No machine translation.
ZH_NAMES = {
  "gates-of-olympus-2500": {
    "zh": "奥林匹斯之门2500",
    "en": "Gates of Olympus 2500",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/gates-of-olympus-2500/",
    "source_title": "奥林匹斯之门2500 (Gates of Olympus 2500)",
    "checked_at": "2026-11-17"
  },
  "gates-of-olympus-super-scatter": {
    "zh": "奥林匹斯之门超神力",
    "en": "Gates of Olympus Super Scatter",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/gates-of-olympus-super-scatter/",
    "source_title": "奥林匹斯之门超神力 (Gates of Olympus Super Scatter)",
    "checked_at": "2026-11-17"
  },
  "sweet-bonanza-2500": {
    "zh": "甜入心扉 2500",
    "en": "Sweet Bonanza 2500",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/sweet-bonanza-2500/",
    "source_title": "甜入心扉 2500 (Sweet Bonanza 2500)",
    "checked_at": "2026-11-17"
  },
  "big-bass-halloween-splash-1000": {
    "zh": "大鲈鱼溅水万圣夜1000",
    "en": "Big Bass Halloween Splash 1000",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/big-bass-halloween-splash-1000/",
    "source_title": "大鲈鱼溅水万圣夜1000 (Big Bass Halloween Splash 1000)",
    "checked_at": "2026-11-17"
  },
  "sugar-rush-1000": {
    "zh": "极速糖果1000",
    "en": "Sugar Rush 1000",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/sugar-rush-1000/",
    "source_title": "极速糖果1000 (Sugar Rush 1000)",
    "checked_at": "2026-11-17"
  },
  "gates-of-olympus-1000": {
    "zh": "奥林匹斯之门 1000",
    "en": "Gates of Olympus 1000™",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/gates-of-olympus-1000/",
    "source_title": "奥林匹斯之门 1000 (Gates of Olympus 1000™)",
    "checked_at": "2026-11-17"
  },
  "sweet-bonanza-1000": {
    "zh": "甜入心扉 1000",
    "en": "Sweet Bonanza 1000",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/sweet-bonanza-1000/",
    "source_title": "甜入心扉 1000 (Sweet Bonanza 1000)",
    "checked_at": "2026-11-17"
  },
  "big-bass-bonanza-1000": {
    "zh": "疯狂大鲈鱼 1000",
    "en": "Big Bass Bonanza 1000",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/big-bass-bonanza-1000/",
    "source_title": "疯狂大鲈鱼 1000 (Big Bass Bonanza 1000)",
    "checked_at": "2026-11-17"
  },
  "sweet-bonanza": {
    "zh": "甜入心扉™",
    "en": "Sweet Bonanza™",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/sweet-bonanza/",
    "source_title": "甜入心扉™ (Sweet Bonanza™)",
    "checked_at": "2026-11-17"
  },
  "gates-of-olympus": {
    "zh": "奥林匹斯之门™",
    "en": "Gates of Olympus™",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/gates-of-olympus/",
    "source_title": "奥林匹斯之门™ (Gates of Olympus™)",
    "checked_at": "2026-11-17"
  },
  "sugar-rush": {
    "zh": "极速糖果",
    "en": "Sugar Rush",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/sugar-rush/",
    "source_title": "极速糖果 (Sugar Rush)",
    "checked_at": "2026-11-17"
  },
  "fruit-party": {
    "zh": "水果派对™",
    "en": "Fruit Party™",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/fruit-party/",
    "source_title": "水果派对™ (Fruit Party™)",
    "checked_at": "2026-11-17"
  },
  "big-bass-christmas-blast-1000": {
    "zh": "疯狂大鲈鱼欢乐爆发 1000",
    "en": "Big Bass Christmas Blast 1000",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/",
    "source_title": "疯狂大鲈鱼欢乐爆发 1000 (Big Bass Christmas Blast 1000)",
    "checked_at": "2026-11-17"
  },
  "zeus-vs-hades-pop": {
    "zh": "宙斯vs哈迪斯 POP",
    "en": "Zeus vs Hades POP",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/",
    "source_title": "宙斯vs哈迪斯 POP (Zeus vs Hades POP)",
    "checked_at": "2026-11-17"
  },
  "super-golden-spins": {
    "zh": "超级大跃金",
    "en": "Super Golden Spins",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/",
    "source_title": "超级大跃金 (Super Golden Spins)",
    "checked_at": "2026-11-17"
  },
  "killer-night": {
    "zh": "暗夜猎杀",
    "en": "Killer Night",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/",
    "source_title": "暗夜猎杀 (Killer Night)",
    "checked_at": "2026-11-17"
  },
  "5-lions-megaways-2": {
    "zh": "5金狮Megaways™ 2",
    "en": "5 Lions Megaways™ 2",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/5-lions-megaways-2/",
    "source_title": "5金狮Megaways™ 2 (5 Lions Megaways™ 2)",
    "source_type": "published_chinese_game_title",
    "checked_at": "2026-11-17"
  },
  "big-bass-vegas-1000": {
    "zh": "至尊疯狂大鲈鱼 1000",
    "en": "Big Bass Vegas 1000",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/big-bass-vegas-1000/",
    "source_title": "至尊疯狂大鲈鱼 1000 (Big Bass Vegas 1000)",
    "source_type": "published_chinese_game_title",
    "checked_at": "2026-11-17"
  },
  "starlight-princess-1000": {
    "zh": "星光公主 1000",
    "en": "Starlight Princess 1000",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/starlight-princess-1000/",
    "source_title": "星光公主 1000 (Starlight Princess 1000)",
    "source_type": "published_chinese_game_title",
    "checked_at": "2026-11-17"
  },
  "wild-west-gold": {
    "zh": "西部牛仔黄金地段™",
    "en": "Wild West Gold™",
    "provider": "pragmatic-play",
    "source": "https://www.ppwinner.com/zh/游戏/wild-west-gold/",
    "source_title": "西部牛仔黄金地段™ (Wild West Gold™)",
    "source_type": "published_chinese_game_title",
    "checked_at": "2026-11-17"
  },
  "land-of-the-free": {
    "zh": "自由之国",
    "en": "Land of The Free",
    "provider": "nolimit-city",
    "source": "https://beto168.com/free-slots/land-of-the-free",
    "source_title": "Land of The Free 中文游戏评测",
    "source_type": "published_chinese_catalog_name",
    "source_quote": "**自由之国** **Nolimit City**",
    "checked_at": "2026-11-17"
  },
  "moon-princess-trinity": {
    "zh": "月亮公主三位一体",
    "en": "Moon Princess Trinity",
    "provider": "playn-go",
    "source": "https://beto168.com/free-slots/moon-princess-trinity",
    "source_title": "Moon Princess Trinity 中文游戏评测",
    "source_type": "published_chinese_catalog_name",
    "source_quote": "月亮公主三位一体",
    "checked_at": "2026-11-17"
  }
}


class BotError(Exception):
    pass


def request_json(url, payload=None, headers=None):
    """Never include a secret-bearing request URL or response in errors."""
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(url, data=data, headers={
        "User-Agent": "curl/8.10.1", "Accept": "application/json",
        "Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        # GETs are safe to repeat. Telegram writes are deliberately not retried.
        raise BotError(f"接口 HTTP {exc.code}；请求失败，未自动重试") from None
    except (URLError, TimeoutError, OSError):
        raise BotError("网络请求失败；若为发送请求，结果可能未知，请先检查频道") from None
    except (ValueError, UnicodeError):
        raise BotError("接口未返回有效 JSON") from None


def number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def parse_rows(data, window):
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise BotError("RTP 接口结构发生变化：缺少 rows")
    rows = []
    for row in data["rows"]:
        if not isinstance(row, dict):
            raise BotError("RTP 行结构无效")
        game = row.get("game") or {}
        if game.get("kind") != "slots":
            continue
        if row.get("window") != window or row.get("scope") != "slot":
            raise BotError("接口返回了错误的统计周期或范围，已停止推送")
        if not re.fullmatch(r"[a-z0-9-]+", game.get("slug", "")):
            raise BotError("游戏标识无效")
        if row.get("rtp") is None:
            continue
        for key in ("rtp", "n", "wagered_usd"):
            if not number(row.get(key)) or row[key] < 0:
                raise BotError(f"RTP 数值无效：{key}")
        if row["wagered_usd"] == 0:
            continue
        rows.append(row)
    return rows


def get_rows(window, limit):
    params = urlencode({"window": window, "scope": "slot", "limit": limit})
    key = os.environ.get("GAMBATRACKER_API_KEY", "").strip()
    data = request_json(f"{BASE}/api/rtp?{params}",
                        headers={"x-api-key": key} if key else {})
    return parse_rows(data, window)


def pct(value):
    return f"{value * 100:.2f}%" if number(value) else "暂无"


def normalized_title(value):
    return " ".join(str(value).replace("™", "").replace("®", "").split()).casefold()


def chinese_name(game):
    record = ZH_NAMES.get(game.get("slug"))
    if not record:
        return None
    provider = game.get("provider") or {}
    if (provider.get("slug") != record["provider"] or
            normalized_title(game.get("name", "")) != normalized_title(record["en"])):
        return None
    return record


def game_title(game):
    name = html.escape(str(game.get("name", game["slug"]))[:100])
    url = f"{BASE}/slots/{game['slug']}"
    record = chinese_name(game)
    if record:
        source = html.escape(quote(record["source"], safe=":/%"), quote=True)
        zh = html.escape(record["zh"])
        title = f'<a href="{source}">{zh}</a>（<a href="{url}">{name}</a>）'
    else:
        title = f'<a href="{url}">{name}</a>（中文名待核实）'
    return title


def entry(row):
    title = game_title(row["game"])
    low, high = row.get("ci_low"), row.get("ci_high")
    band = f"{pct(low)}–{pct(high)}" if number(low) and number(high) else "暂无"
    sample = "样本达标" if row.get("enough_sample") is True else "样本不足"
    return (f'{title}\n'
            f'观测 {pct(row["rtp"])}｜官方 {pct(row.get("official_rtp"))}\n'
            f'{int(row["n"]):,}笔｜{sample}｜95%区间 {band}')


def utf16len(text):
    return len(text.encode("utf-16-le")) // 2


def beijing_time(value):
    return value.astimezone(BEIJING_TIMEZONE).strftime("%m-%d %H:%M:%S")


def make_messages(snapshots, config):
    blocks = ["<b>老虎机 RTP 观测汇总</b>",
              "各周期仅从已核实中文名的游戏中按投注笔数选取；非全站完整排名。",
              "中文名取自已核实中文游戏页面，点击中文名可查看出处；英文名链接为 RTP 来源。"]
    slugs = set(config.get("game_slugs", []))
    any_games = False
    for window, rows, fetched in snapshots:
        if slugs:
            rows = [r for r in rows if r["game"]["slug"] in slugs]
        rows = [r for r in rows if chinese_name(r["game"])]
        rows = sorted(rows, key=lambda r: r["n"], reverse=True)[:config["top_n"]]
        any_games = any_games or bool(rows)
        blocks.append(f"<b>{LABELS[window]}</b> · 抓取 {beijing_time(fetched)} 北京时间")
        blocks.extend(entry(row) for row in rows)
        if not rows:
            blocks.append("本次返回列表中暂无已核实中文名的匹配游戏。")
    if not any_games:
        return []
    blocks.extend(["观测样本可能不完整；历史 RTP 不预测下一次结果。",
                   '实时RTP查询机器人：<a href="https://t.me/RTPzhushouBOT">@RTPzhushouBOT</a>'])
    return split_messages(blocks)


def split_messages(blocks):
    messages, current = [], ""
    for block in blocks:
        candidate = current + ("\n\n" if current else "") + block
        # Bound raw HTML too: stricter than Telegram's parsed-text limit.
        if utf16len(candidate) > 3500:
            messages.append(current)
            current = block
        else:
            current = candidate
    if current:
        messages.append(current)
    if len(messages) > 1:
        attribution = '\n\n实时RTP查询机器人：<a href="https://t.me/RTPzhushouBOT">@RTPzhushouBOT</a>'
        messages = [m + attribution for m in messages]
    return messages


def make_hourly_messages(snapshots, config):
    tables = {w: {r["game"]["slug"]: r for r in rows} for w, rows, _ in snapshots}
    active = sorted(tables.get("24h", {}).values(), key=lambda r: r["n"], reverse=True)
    wanted = set(config.get("game_slugs", []))
    if wanted:
        active = [r for r in active if r["game"]["slug"] in wanted]
    active = [r for r in active if chinese_name(r["game"])]
    if not active:
        return []
    blocks = ["<b>每小时 · 活跃老虎机 RTP</b>",
              "从近24小时列表中，仅选中文名已核实的活跃游戏，最多5款，非全站完整排名。",
              "中文名可点击查看出处；英文名链接为 RTP 页面。"]
    blocks.append("抓取时间（北京时间，UTC+8）：\n" + "\n".join(
        f"{LABELS[w]} {beijing_time(fetched)}" for w, _, fetched in snapshots))
    for row in active[:5]:
        slug = row["game"]["slug"]
        lines = [game_title(row["game"]), f"官方 RTP：{pct(row.get('official_rtp'))}"]
        for window in ("10m", "1h", "24h"):
            item = tables.get(window, {}).get(slug)
            if item is None:
                lines.append(f"{LABELS[window]}：本次返回列表未包含，暂无可用值")
                continue
            flag = "样本达标" if item.get("enough_sample") is True else "样本不足"
            band = f"{pct(item.get('ci_low'))}–{pct(item.get('ci_high'))}"
            lines.append(f"{LABELS[window]}：{pct(item['rtp'])} · {int(item['n']):,}笔 · {flag}\n95%区间：{band}")
        blocks.append("\n".join(lines))
    if not active:
        blocks.append("本次返回列表中暂无匹配的老虎机数据。")
    blocks.extend(["公开观测样本可能不完整；历史 RTP 不预测下一次结果。",
                   '实时RTP查询机器人：<a href="https://t.me/RTPzhushouBOT">@RTPzhushouBOT</a>'])
    return split_messages(blocks)


def telegram(token, method, payload):
    answer = request_json(f"https://api.telegram.org/bot{token}/{method}", payload)
    if not isinstance(answer, dict) or answer.get("ok") is not True:
        raise BotError("Telegram 拒绝请求，请检查 Token 和频道权限")
    return answer["result"]


def check_channel(token, config):
    me = telegram(token, "getMe", {})
    if me.get("username", "").lower() != config["expected_bot"].lstrip("@").lower():
        raise BotError("Token 对应的机器人不是配置中的机器人")
    channel = telegram(token, "getChat", {"chat_id": config["channel"]})
    if channel.get("type") != "channel":
        raise BotError("目标不是 Telegram 频道")
    member = telegram(token, "getChatMember", {
        "chat_id": channel["id"], "user_id": me["id"]})
    if member.get("status") != "creator" and not (
            member.get("status") == "administrator" and member.get("can_post_messages") is True):
        raise BotError("请将机器人设为频道管理员并开启发布消息权限")
    return channel["id"]


def validate_config(config):
    windows = config.get("windows", [])
    if not windows or len(windows) != len(set(windows)) or any(w not in LABELS for w in windows):
        raise BotError("windows 必须是支持的、不重复的统计周期")
    if not isinstance(config.get("top_n"), int) or not 1 <= config["top_n"] <= 10:
        raise BotError("top_n 必须在 1–10 之间")
    if not isinstance(config.get("fetch_limit"), int) or not 1 <= config["fetch_limit"] <= 200:
        raise BotError("fetch_limit 必须在 1–200 之间")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="实际发送；默认只生成预览")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--hourly", action="store_true", help="5款游戏的10m/1h/24h对照汇总")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    validate_config(config)
    config["channel"] = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or config["channel"]
    snapshots = []
    # Fetch everything successfully before sending any messages.
    windows = ["10m", "1h", "24h"] if args.hourly else config["windows"]
    for window in windows:
        rows = get_rows(window, config["fetch_limit"])
        snapshots.append((window, rows, datetime.now(timezone.utc)))
    messages = (make_hourly_messages if args.hourly else make_messages)(snapshots, config)
    preview = Path("preview")
    preview.mkdir(exist_ok=True)
    for index, message in enumerate(messages, 1):
        (preview / f"message-{index}.html").write_text(message, encoding="utf-8")
    if not args.send:
        print(f"仅生成预览，共 {len(messages)} 条；未连接 Telegram，未发送消息。")
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise BotError("请在 GitHub Secrets 中设置 TELEGRAM_BOT_TOKEN")
    channel_id = check_channel(token, config)
    for index, message in enumerate(messages, 1):
        telegram(token, "sendMessage", {
            "chat_id": channel_id, "text": message, "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True}})
        print(f"已发送 {index}/{len(messages)}")
        if index < len(messages):
            time.sleep(1.1)


if __name__ == "__main__":
    try:
        main()
    except (BotError, ValueError, KeyError, OSError) as exc:
        # Only safe, authored errors are printed; never leak HTTP request URLs.
        print(str(exc) if isinstance(exc, BotError) else f"配置或数据错误：{type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
