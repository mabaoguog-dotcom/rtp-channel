"""Build a game-specific, factual payout poster from the source game artwork."""
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont, ImageOps

import bot

FONT = Path(__file__).parent / "assets/rtp-poster-font.otf"
Image.MAX_IMAGE_PIXELS = 16_000_000


def cover(game):
    manifest_path = Path(__file__).parent / "game-covers-zh/index.json"
    if manifest_path.exists():
        entry = json.loads(manifest_path.read_text()).get(game.get("slug"))
        if (entry and entry["provider"] == (game.get("provider") or {}).get("slug") and
                bot.normalized_title(entry["en"]) == bot.normalized_title(game.get("name", ""))):
            try:
                with Image.open(manifest_path.parent / entry["file"]) as image:
                    image.load()
                    return image.convert("RGB")
            except (OSError, ValueError):
                pass
    url = urljoin(bot.BASE, str(game.get("thumb") or ""))
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "gambatracker.com" or
            not parsed.path.startswith("/media/games/")):
        return None
    try:
        with urlopen(Request(url, headers={"User-Agent": "curl/8.10.1"}), timeout=15) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            return None
        with Image.open(BytesIO(raw)) as image:
            image.load()
            return image.convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def money(value):
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:,.2f}亿美元"
    if abs(value) >= 10_000:
        return f"{value / 10_000:,.2f}万美元"
    return f"{value:,.2f}美元"


def make_poster(bet, artwork=None):
    image = Image.new("RGB", (1280, 800), "#0a0b0d")
    draw = ImageDraw.Draw(image)
    font = lambda size: ImageFont.truetype(str(FONT), size)

    def text(xy, value, size=24, color="#ebede8", width=None):
        while width and size > 16 and draw.textlength(str(value), font=font(size)) > width:
            size -= 1
        draw.text(xy, str(value), font=font(size), fill=color)

    for y in range(800):
        shade = max(10, 21 - y // 70)
        draw.line((0, y, 1280, y), fill=(shade, shade + 1, shade + 3))
    for y in range(3):
        for x in range(3):
            draw.ellipse((49 + x * 13, 40 + y * 13, 56 + x * 13, 47 + y * 13),
                         fill="#f2b134" if x == y == 1 else "#737771")
    text((103, 31), "RTP助手", 32)
    text((1010, 43), "高倍爆奖", 24, "#f2b134")
    draw.line((48, 104, 1232, 104), fill="#34332c", width=2)
    draw.rounded_rectangle((48, 139, 432, 694), radius=18, fill="#171a1d", outline="#34383e", width=2)
    if artwork is not None:
        art = ImageOps.contain(artwork, (348, 510), Image.Resampling.LANCZOS)
        image.paste(art, (66 + (348 - art.width) // 2, 160 + (510 - art.height) // 2))
    else:
        text((101, 337), "游戏封面暂无", 32, "#92968f")
        text((90, 393), bet["game"].get("name", ""), 25, width=300)
    game = bet["game"]
    record = bot.chinese_name(game)
    text((480, 138), record["zh"] if record else game["name"], 38, width=742)
    text((482, 202), game["name"], 24, "#92968f", width=740)
    text((482, 268), "赢奖倍数", 23, "#aeb2ab")
    text((477, 304), f"{bet['multiplier']:,.2f}倍", 67, "#f2b134", width=747)
    draw.line((480, 414, 1232, 414), fill="#303339", width=2)
    fields = [(480, "派彩金额", money(bet["payout_usd"])),
              (858, "投注金额", money(bet["amount_usd"]))]
    for x, label, value in fields:
        text((x, 445), label, 21, "#92968f")
        text((x, 483), value, 33, width=350)
    text((480, 564), "本笔净赢", 21, "#92968f")
    text((480, 602), money(bet["payout_usd"] - bet["amount_usd"]), 33, "#62d6a2", width=735)
    casino = str((bet.get("casino") or {}).get("name") or "未知赌场")
    casino = " ".join(casino.split())[:100]
    text((480, 663), "赌场：" + casino, 24, "#aeb2ab", width=740)
    stamp = bot.datetime.fromisoformat(bet["ts"].replace("Z", "+00:00"))
    text((48, 724), "事件时间 " + bot.beijing_time(stamp) + " 北京时间", 18, "#92968f")
    text((48, 760), "公开观测历史记录，不预测下一次结果。", 16, "#92968f")
    text((905, 746), "@RTPZSBOT", 22, "#f2b134")
    output = BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()


def prepare_poster(bet):
    return make_poster(bet, cover(bet["game"]))


def prepare_hourly_poster(snapshots, config):
    """Use only the first game's original cover; keep RTP facts in the caption."""
    row = bot.hourly_first(snapshots, config)
    if row is None:
        return None
    artwork = cover(row["game"])
    if artwork is None:
        return None
    # Telegram photo dimensions are bounded without adding text or another game's art.
    artwork.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
    out = BytesIO()
    artwork.save(out, format="JPEG", quality=95, optimize=True)
    return out.getvalue()
