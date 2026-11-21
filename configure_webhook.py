"""Keep Bot Token in Actions; transfer only an RSA-sealed webhook verifier."""
import hashlib
import hmac
import os
from pathlib import Path
import subprocess

import bot

URL='https://rtpbodon-data.pluckyegret35.chatgpt.site/bot/webhook'
CONTEXT=b'rtpzsbot-webhook-verification-v1'


def main():
    token=os.environ['TELEGRAM_BOT_TOKEN']
    operation=os.environ.get('WEBHOOK_OPERATION','status')
    me=bot.telegram(token,'getMe',{})
    if me.get('username','').lower()!='rtpzsbot':raise bot.BotError('机器人身份不匹配')
    if operation=='prepare':
        verifier=hmac.new(token.encode(),CONTEXT,hashlib.sha256).hexdigest()
        try:
            sealed=subprocess.run(['openssl','pkeyutl','-encrypt','-pubin','-inkey','webhook-transfer-public.pem',
                                   '-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256'],
                                  input=verifier.encode(),capture_output=True,check=True).stdout
        except Exception:raise bot.BotError('验证值封装失败，未输出任何凭证') from None
        Path('sealed-webhook-verifier.bin').write_bytes(sealed)
        print('Prepared encrypted webhook verifier. Bot Token remains in GitHub Actions.')
        return
    if operation=='activate':
        verifier=hmac.new(token.encode(),CONTEXT,hashlib.sha256).hexdigest()
        bot.telegram(token,'setWebhook',{'url':URL,'secret_token':verifier,'allowed_updates':['message'],
                                        'drop_pending_updates':False,'max_connections':10})
    elif operation!='status':raise bot.BotError('未知配置操作')
    state=bot.telegram(token,'getWebhookInfo',{})
    if operation=='activate' and state.get('url')!=URL:raise bot.BotError('Webhook地址核验失败')
    print('Verified bot:',me['username'])
    print('Webhook URL:',state.get('url',''))
    print('Pending updates:',state.get('pending_update_count',0))
    print('Webhook delivery error:',state.get('last_error_message','none'))


if __name__=='__main__':
    try:main()
    except bot.BotError as exc:raise SystemExit(str(exc)) from None
