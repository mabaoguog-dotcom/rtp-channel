"""Replace only the old bot attribution in public channel history."""
from html.parser import HTMLParser
import html
import json
import os
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import bot

OLD = 'RTPzhushouBOT'
NEW = 'RTPZSBOT'


class TelegramHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
    def handle_starttag(self, tag, attrs):
        if tag == 'br': self.out.append('\n')
        elif tag == 'a':
            href = dict(attrs).get('href', '')
            self.out.append('<a href="' + html.escape(href, quote=True) + '">')
        elif tag in ('b','strong','i','em','u','s','strike','del','code','pre','blockquote'):
            self.out.append('<' + tag + '>')
    def handle_endtag(self, tag):
        if tag in ('a','b','strong','i','em','u','s','strike','del','code','pre','blockquote'):
            self.out.append('</' + tag + '>')
    def handle_data(self, data): self.out.append(html.escape(data))


def replacements(page):
    found = []
    for section in re.split(r'(?=<div class="tgme_widget_message_wrap)', page):
        identity = re.search(r'data-post="rtpbodon/(\d+)"', section)
        text = re.search(r'<div class="tgme_widget_message_text[^\"]*"[^>]*>(.*?)</div>', section, re.S)
        if not identity or not text or OLD.lower() not in text[1].lower():
            continue
        parser = TelegramHTML(); parser.feed(text[1]); original = ''.join(parser.out)
        updated = re.sub(OLD, NEW, original, flags=re.I)
        # Keep every other visible character, including the historical record.
        if updated == original:
            continue
        photo = 'tgme_widget_message_photo_wrap' in section or 'tgme_widget_message_video_wrap' in section
        found.append({'message_id': int(identity[1]), 'content': updated, 'photo': photo})
    return found


def edit_footer(token, method, payload):
    # Editing the same post to the same contents is idempotent. Only retry an
    # explicit Telegram rate-limit rejection; do not retry unknown outcomes.
    request = Request('https://api.telegram.org/bot' + token + '/' + method,
                      data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                answer = json.load(response)
            if answer.get('ok'):
                return
            raise bot.BotError('Telegram未确认历史帖子修改')
        except HTTPError as exc:
            try: error = json.load(exc)
            except (ValueError, OSError): error = {}
            if exc.code == 400 and 'message is not modified' in error.get('description', ''):
                return
            if exc.code == 429 and attempt < 2:
                delay = min(60, max(1, int(error.get('parameters', {}).get('retry_after', 30))))
                print('Telegram限流，等待后继续', flush=True)
                time.sleep(delay)
                continue
            raise bot.BotError('历史帖子修改请求被拒绝，HTTP ' + str(exc.code)) from None
        except (URLError, OSError, ValueError):
            raise bot.BotError('历史帖子修改结果未知，未自动重试') from None


def main():
    token = os.environ['TELEGRAM_BOT_TOKEN']
    me = bot.telegram(token, 'getMe', {})
    if me.get('username', '').lower() != NEW.lower():
        raise bot.BotError('机器人身份不符，未修改')
    member = bot.telegram(token, 'getChatMember', {'chat_id':'@rtpbodon','user_id':me['id']})
    if member.get('status') != 'creator' and member.get('can_edit_messages') is not True:
        raise bot.BotError('新机器人缺少编辑频道消息权限，未修改历史帖子')
    before, seen, records = None, set(), {}
    for _ in range(100):
        url = 'https://t.me/s/rtpbodon' + (('?before='+str(before)) if before else '')
        page = urlopen(url, timeout=30).read().decode()
        ids = [int(x) for x in re.findall(r'data-post="rtpbodon/(\d+)"',page)]
        if not ids: break
        for item in replacements(page): records[item['message_id']] = item
        low = min(ids)
        if low <= 1 or low in seen: break
        seen.add(low); before = low
    print('找到需更新历史帖子：',len(records), flush=True)
    succeeded, failed = 0, []
    for identity, item in sorted(records.items()):
        payload = {'chat_id':'@rtpbodon','message_id':identity,'parse_mode':'HTML'}
        method = 'editMessageCaption' if item['photo'] else 'editMessageText'
        payload['caption' if item['photo'] else 'text'] = item['content']
        if not item['photo']: payload['link_preview_options']={'is_disabled':True}
        try:
            edit_footer(token,method,payload)
            succeeded += 1
            print('已更新帖子',identity,flush=True)
        except bot.BotError:
            failed.append(identity)
            print('未能更新帖子',identity,flush=True)
        time.sleep(3.2)
    print(json.dumps({'updated':succeeded,'failed':failed},ensure_ascii=False))
    if failed: raise bot.BotError('部分历史帖子无法修改；未删除或重新发布')


if __name__ == '__main__':
    try: main()
    except bot.BotError as exc: raise SystemExit(str(exc)) from None
