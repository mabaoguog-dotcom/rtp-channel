"""Set only @shiwanceshiBOT menu after identity verification; never use production token."""
import argparse,json,os,sys
from urllib.request import Request,urlopen
from urllib.error import URLError,HTTPError
URL='https://rtp-freeplay-test.pluckyegret35.chatgpt.site/#freeplay'
def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
 if not a.apply:print('仅预览：将给 @shiwanceshiBOT 配置“打开试玩测试”菜单；没有调用Telegram。');return
 token=os.environ.get('TELEGRAM_TEST_BOT_TOKEN','').strip()
 if not token:raise RuntimeError('请在测试运行环境配置 TELEGRAM_TEST_BOT_TOKEN；不要贴在聊天中。')
 def call(method,payload):
  try:
   with urlopen(Request('https://api.telegram.org/bot'+token+'/'+method,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'}),timeout=20) as r:v=json.load(r)
  except (URLError,HTTPError,ValueError):raise RuntimeError('Telegram测试配置请求失败；没有输出密钥或请求URL。') from None
  if not v.get('ok'):raise RuntimeError('Telegram拒绝测试配置请求。')
  return v['result']
 me=call('getMe',{})
 if me.get('username','').lower()!='shiwanceshibot':raise RuntimeError('机器人身份不符，已阻止所有配置写入。')
 call('setChatMenuButton',{'menu_button':{'type':'web_app','text':'打开试玩测试','web_app':{'url':URL}}})
 print('已配置 @shiwanceshiBOT 测试菜单；正式机器人未修改。')
if __name__=='__main__':
 try:main()
 except RuntimeError as e:print(str(e),file=sys.stderr);sys.exit(1)
