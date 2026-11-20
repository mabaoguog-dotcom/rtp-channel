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
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    me = bot.telegram(token, "getMe", {})
    if me.get("username", "").lower() != "rtpzsbot":
        raise bot.BotError("Token对应的机器人不匹配")
    if bot.telegram(token, "getWebhookInfo", {}).get("url"):
        raise bot.BotError("已有Webhook，未启动轮询以避免冲突")
    updates = bot.telegram(token, "getUpdates", {"timeout": 0, "limit": 100, "allowed_updates": ["message"]})
    count = 0
    for update in updates:
        message = update.get("message") or {}
        if message.get("chat", {}).get("type") != "private":
            continue
        payload = start_reply(message)
        text = message.get("text")
        if payload:
            replies = [("sendMessage", payload)]
        elif text == "返回菜单":
            replies = [("sendMessage", {"text":"请选择功能", "reply_markup":MENU})]
        elif isinstance(text, str):
            try:
                replies = query_replies(text)
            except bot.BotError:
                replies = [("sendMessage", {"text":"本次数据暂时读取失败，请稍后查询，或直接打开数据站。"})]
        else:
            continue
        for method, reply in replies:
            reply["chat_id"] = message["chat"]["id"]
            try:
                bot.telegram(token, method, reply)
                count += 1
            except bot.BotError:
                print("一条私聊回复未确认，继续处理其他请求；未记录聊天内容")
    if updates:
        bot.telegram(token, "getUpdates", {"offset": max(u["update_id"] for u in updates) + 1,
                                          "timeout": 0, "limit": 1, "allowed_updates": ["message"]})
    print(f"已处理私聊回复：{count}条；未记录聊天内容")


if __name__ == "__main__":
    try:
        main()
    except bot.BotError as exc:
        raise SystemExit(str(exc)) from None
