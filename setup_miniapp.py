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
    if bot.get("username", "").lower() != "rtpzhushoubot":
        raise SystemExit("Configured token does not belong to the expected bot.")
    button = {"type": "web_app", "text": "打开数据站", "web_app": {"url": APP_URL}}
    api("setChatMenuButton", {"menu_button": button})
    current = api("getChatMenuButton")
    if current.get("type") != "web_app" or current.get("web_app", {}).get("url", "").rstrip("/") != APP_URL.rstrip("/"):
        raise SystemExit("Telegram menu verification failed.")
    print("Verified @" + bot["username"] + " menu: 打开数据站 -> " + APP_URL)


if __name__ == "__main__":
    main()
