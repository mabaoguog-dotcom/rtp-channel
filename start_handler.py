"""Reply to explicit /start requests without storing chat contents in GitHub."""
import os
import re

import bot
from chat_queries import MENU, query_replies

APP_URL = "https://rtpbodon-data.pluckyegret35.chatgpt.site"


def start_reply(message):
    if not isinstance(message, dict) or message.get("chat", {}).get("type") != "private":
        return None
    text = message.get("text", "")
    if not isinstance(text, str) or not re.fullmatch(r"/start(?:@RTPZSBOT)?(?:\s+[^\r\n]*)?", text, re.I):
        return None
    return {"chat_id": message["chat"]["id"],
            "text": "欢迎使用 RTP助手！\n\n查询老虎机观测RTP、比较游戏，查看月报、最大爆奖和最大倍数。\n\n点击下方聊天按钮查询，或点击「打开数据站」进入小程序。\n\n公开历史样本，不预测下一次结果。",
            "reply_markup": MENU}


def main():
    print("聊天已切换Webhook即时接收；GitHub轮询入口已停用。")


if __name__ == "__main__":
    try:
        main()
    except bot.BotError as exc:
        raise SystemExit(str(exc)) from None
