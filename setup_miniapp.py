"""Configure the bot's private-chat Mini App menu; credentials stay in Actions."""
import json
import os
import urllib.request

APP_URL = "https://rtpbodon-data.pluckyegret35.chatgpt.site"


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    def api(method, data=None):
        request = urllib.request.Request(
            "https://api.telegram.org/bot" + token + "/" + method,
            data=json.dumps(data or {}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except Exception:
            raise SystemExit("Telegram API request failed; token omitted from logs.") from None
        if not result.get("ok"):
            raise SystemExit("Telegram rejected the menu operation.")
        return result["result"]

    bot = api("getMe")
    if bot.get("username", "").lower() != "rtpzsbot":
        raise SystemExit("Configured token does not belong to the expected bot.")
    api("setMyName", {"name": "RTP助手"})
    channel = api("getChat", {"chat_id": "@rtpbodon"})
    member = api("getChatMember", {"chat_id": channel["id"], "user_id": bot["id"]})
    if member.get("status") != "creator" and not (member.get("status") == "administrator" and member.get("can_post_messages") is True):
        raise SystemExit("New bot needs channel administrator permission to post messages.")
    print("Verified new bot channel posting permission.")
    button = {"type": "web_app", "text": "打开数据站", "web_app": {"url": APP_URL}}
    api("setChatMenuButton", {"menu_button": button})
    current = api("getChatMenuButton")
    if current.get("type") != "web_app" or current.get("web_app", {}).get("url", "").rstrip("/") != APP_URL.rstrip("/"):
        print("Returned menu:", json.dumps(current, ensure_ascii=False))
        raise SystemExit("Telegram menu verification failed.")
    description = ("RTP助手｜老虎机公开数据查询\n\n"
                   "可查看近10分钟、1小时、24小时等周期的观测RTP，比较2–3款老虎机，"
                   "浏览月报、最大爆奖与最大倍数记录。频道每小时发布活跃排行第1名，"
                   "大额派彩附对应游戏海报。\n\n"
                   "如何打开：\n1. 点击「开始」进入机器人。\n"
                   "2. 点击聊天输入框左侧的「打开数据站」。\n"
                   "3. 在小程序内搜索游戏或选择底部分类。\n\n"
                   "频道：@rtpbodon\n公开历史样本，不预测下一次结果。")
    short = "查询老虎机RTP、游戏比较、月报和爆奖记录。进入聊天后，点击左下角「打开数据站」使用小程序。频道：@rtpbodon"
    api("setMyDescription", {"description": description})
    api("setMyDescription", {"description": description, "language_code": "zh"})
    api("setMyShortDescription", {"short_description": short})
    api("setMyShortDescription", {"short_description": short, "language_code": "zh"})
    if api("getMyDescription").get("description") != description:
        raise SystemExit("Bot description verification failed.")
    if api("getMyShortDescription").get("short_description") != short:
        raise SystemExit("Bot short description verification failed.")
    print("Verified bot introduction and opening instructions.")
    print("Verified @" + bot["username"] + " menu: 打开数据站 -> " + APP_URL)


if __name__ == "__main__":
    main()
