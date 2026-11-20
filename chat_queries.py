"""Read-only private-chat queries; public name evidence stays bundled with code."""
from datetime import datetime, timezone
from functools import lru_cache
import html
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlencode

import bot
from game_poster import prepare_hourly_poster, prepare_poster

APP_URL = 'https://rtpbodon-data.pluckyegret35.chatgpt.site'
MENU = {'keyboard': [[{'text':'📊 实时RTP'}, {'text':'🥇 活跃第一名'}],
                     [{'text':'💰 最新大额派彩'}, {'text':'🔎 搜索游戏'}],
                     [{'text':'📱 打开数据站','web_app':{'url':APP_URL}}, {'text':'❓ 使用说明'}]],
        'resize_keyboard':True, 'is_persistent':True, 'input_field_placeholder':'选择功能，或输入中文/英文游戏名'}


def normalize(value):
    value = unicodedata.normalize('NFKC', str(value).replace('™','').replace('®','')).lower()
    return ''.join(c for c in value if c.isalnum())


@lru_cache(maxsize=1)
def names():
    return json.loads(Path(__file__).with_name('game_names.json').read_text())


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('game_catalog.json').read_text())


def matches(game, query):
    record = names().get(game['slug'], {})
    if record and (record.get('provider') != (game.get('provider') or {}).get('slug') or normalize(record.get('en')) != normalize(game.get('name'))):
        record = {}
    fields = [game.get('name'), record.get('zh'), *record.get('aliases', [])]
    return any(normalize(query) in normalize(value) for value in fields if value)


def web_button(view='home', label='查看更多'):
    return {'inline_keyboard':[[{'text':label,'web_app':{'url':APP_URL+'#'+view}}]]}


@lru_cache(maxsize=8)
def rows(window):
    return bot.get_rows(window, 200)


def text_result(text, view='home'):
    return [('sendMessage', {'text':text, 'parse_mode':'HTML', 'reply_markup':web_button(view)})]


def snapshots():
    return [(w, rows(w), datetime.now(timezone.utc)) for w in ('10m','1h','24h')]


@lru_cache(maxsize=50)
def game_rtp(slug):
    try:
        detail=bot.request_json(bot.BASE+'/api/games/'+slug+'?window=30d')
        return {r['window']:r for r in detail.get('rtp',[]) if not r.get('casino')}
    except bot.BotError:
        return {}


def search(query):
    q=normalize(query)
    if len(q)<2 or len(query)>100:
        return text_result('请输入至少两个字的中文名或英文名，例如：甜入心扉、奥林匹斯。')
    found=[g for g in catalog() if matches(g, query)]
    if not found:
        translated=next((r['en'] for r in names().values() if any(q in normalize(v) for v in [r['zh'],*r.get('aliases',[])])),query)
        result=bot.request_json(bot.BASE+'/api/search?'+urlencode({'q':translated}))
        found=[g for g in result.get('games',[]) if g.get('kind')=='slots' and matches(g,query)]
    if not found:
        return text_result('没有找到匹配游戏。部分游戏中文名尚未核实，可换用英文名。')
    blocks=['<b>游戏搜索结果</b>（最多显示3款）']
    tables={w:{r['game']['slug']:r for r in rows(w)} for w in ('10m','1h','24h')}
    for game in found[:3]:
        record=names().get(game['slug'])
        label=(record['zh']+'（'+game['name']+'）') if record else game['name']
        lines=[html.escape(label)]
        detail=game_rtp(game['slug']) if game['slug'] not in tables['24h'] else {}
        for w, table in tables.items():
            r=table.get(game['slug']) or detail.get(w)
            lines.append(bot.LABELS[w]+'：'+(bot.pct(r['rtp'])+f" · {int(r['n']):,}笔" if r else '本次样本列表未包含'))
        blocks.append('\n'.join(lines))
    blocks.append('公开历史观测样本，不预测下一次结果。')
    return text_result('\n\n'.join(blocks),'rtp')


def query_replies(text):
    if text in ('📊 实时RTP','实时RTP','/rtp'):
        keyboard={'keyboard':[[{'text':'10分钟RTP'},{'text':'1小时RTP'},{'text':'24小时RTP'}],[{'text':'返回菜单'}]],'resize_keyboard':True}
        return [('sendMessage', {'text':'选择观测周期。按样本投注笔数显示前3款已核实中文名的游戏，非收益预测。','reply_markup':keyboard})]
    if text in ('10分钟RTP','1小时RTP','24小时RTP'):
        window={'10分钟RTP':'10m','1小时RTP':'1h','24小时RTP':'24h'}[text]
        selected=sorted((r for r in rows(window) if bot.chinese_name(r['game'])),key=lambda r:r['n'],reverse=True)[:3]
        blocks=['<b>'+bot.LABELS[window]+' RTP观测</b>']+[bot.entry(r) for r in selected]
        if not selected: blocks.append('当前返回列表暂无已核实中文名的游戏。')
        blocks.append('抓取：'+bot.beijing_time(datetime.now(timezone.utc))+' 北京时间\n公开样本，不预测下一次结果。')
        return text_result('\n\n'.join(blocks),'rtp')
    if text in ('🥇 活跃第一名','活跃第一名','/first'):
        data=snapshots(); messages=bot.make_hourly_messages(data,{})
        if not messages:return text_result('当前暂无可展示的已核实游戏。','rtp')
        poster=prepare_hourly_poster(data,{})
        if poster:return [('sendPhoto',{'photo':poster,'caption':messages[0],'parse_mode':'HTML','reply_markup':web_button('rtp')})]
        return text_result(messages[0],'rtp')
    if text in ('💰 最新大额派彩','最新大额派彩','/wins'):
        from github_poller import eligible, timestamp, big_win_caption
        result=bot.request_json(bot.BASE+'/api/bets?feed=big-wins&window=1h&limit=200')
        now=datetime.now(timezone.utc).timestamp()
        bets=[b for b in result.get('bets',[]) if eligible(b,now)]
        if not bets:return text_result('近1小时返回样本中暂无中文名已核实、派彩不少于1万美元的净赢记录。','maxwins')
        b=max(bets,key=timestamp)
        return [('sendPhoto',{'photo':prepare_poster(b),'caption':big_win_caption(b,now),'parse_mode':'HTML','reply_markup':web_button('maxwins')})]
    if text in ('🔎 搜索游戏','搜索游戏','/search'):
        return text_result('直接发送中文或英文游戏名即可查询，例如：甜入心扉、奥林匹斯、Sweet Bonanza。\n支持部分名称及已核实名称的繁体写法。')
    if text in ('❓ 使用说明','使用说明','/help'):
        return text_result('RTP助手提供：多周期观测RTP、活跃第一名、最新大额派彩和中英文游戏搜索。\n\n完整游戏比较与月报请打开数据站。\n\n当前聊天查询由GitHub定时处理，可能延迟；左下角「打开数据站」可直接使用。\n历史样本不完整，不预测下一次结果。')
    if text.startswith('/') and not text.startswith('/search '):return []
    return search(text.removeprefix('/search ').strip())
