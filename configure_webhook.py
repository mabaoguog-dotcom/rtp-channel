"""Configure Telegram directly; the Bot Token never leaves GitHub for a Site."""
import os
import bot

URL='https://rtpbodon-data.pluckyegret35.chatgpt.site/bot/webhook'


def main():
    token=os.environ['TELEGRAM_BOT_TOKEN']
    secret=os.environ['TELEGRAM_WEBHOOK_SECRET']
    if not 32<=len(secret)<=256:
        raise bot.BotError('Webhook验证密钥未配置')
    me=bot.telegram(token,'getMe',{})
    if me.get('username','').lower()!='rtpzsbot':
        raise bot.BotError('机器人身份不匹配')
    bot.telegram(token,'setWebhook',{'url':URL,'secret_token':secret,'allowed_updates':['message'],
                                    'drop_pending_updates':False,'max_connections':10})
    state=bot.telegram(token,'getWebhookInfo',{})
    if state.get('url')!=URL:raise bot.BotError('Webhook地址核验失败')
    print('Verified @RTPZSBOT webhook:',state['url'])
    print('Pending updates:',state.get('pending_update_count',0))
    print('Webhook has delivery error:',bool(state.get('last_error_date')))


if __name__=='__main__':
    try:main()
    except bot.BotError as exc:raise SystemExit(str(exc)) from None
