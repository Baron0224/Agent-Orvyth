"""DeepSeek official SSE transport. No retries, redirects, key logging or local fallback."""
import json,os,urllib.request,urllib.error
PREFIX='deepseek-cloud:'
ENDPOINT='https://api.deepseek.com/chat/completions'
def is_cloud(model):return model.startswith(PREFIX)
def error_message(code):
 return {401:'DeepSeek密钥验证失败（401），请在本机重新配置密钥。',402:'DeepSeek账户余额不足（402），请自行检查余额。',429:'DeepSeek请求限流（429），本次未重试，请稍后再试。',400:'DeepSeek请求参数无效（400），本次未重试。',422:'DeepSeek请求参数无效（422），本次未重试。'}.get(code,f'DeepSeek服务请求失败（HTTP {code}），本次未重试。')
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
class CloudResponse:
 def __init__(self,response):self.response=response
 def __enter__(self):return self
 def __exit__(self,*args):self.response.close()
 def __iter__(self):
  finish=None;usage={};data=[]
  for raw in self.response:
   line=raw.decode('utf8').rstrip('\r\n')
   if line.startswith(':'):continue
   if line.startswith('data:'):data.append(line[5:].lstrip());continue
   if line or not data:continue
   payload='\n'.join(data);data=[]
   if payload=='[DONE]':
    if finish!='stop':raise RuntimeError('DeepSeek回复未完整结束（截断、过滤或缺少结束标记），本次不保存。')
    yield (json.dumps({'done':True,'usage':usage})+'\n').encode();return
   try:event=json.loads(payload)
   except ValueError:raise RuntimeError('DeepSeek返回的流式数据无法读取，本次不保存。') from None
   if event.get('error'):raise RuntimeError('DeepSeek返回错误，本次不保存且未重试。')
   if isinstance(event.get('usage'),dict):usage={k:v for k,v in event['usage'].items() if k in ('prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens') and isinstance(v,int) and v>=0}
   for choice in event.get('choices',[]):
    if choice.get('finish_reason'):finish=choice['finish_reason']
    content=choice.get('delta',{}).get('content')
    if isinstance(content,str) and content:yield (json.dumps({'message':{'content':content}},ensure_ascii=False)+'\n').encode('utf8')
  raise RuntimeError('DeepSeek连接在完整结束前中断，本次不保存。')
def open_chat(messages,model):
 key=os.environ.get('DEEPSEEK_API_KEY','').strip()
 if not key:raise RuntimeError('未配置DeepSeek密钥。请在本机运行 training/chat_cloud.cmd 隐藏输入，不要将密钥发到聊天。')
 try:limit=int(os.environ.get('ORVYTH_CLOUD_MAX_TOKENS','512'))
 except ValueError:raise RuntimeError('ORVYTH_CLOUD_MAX_TOKENS必须是16到2048的整数。') from None
 if not 16<=limit<=2048:raise RuntimeError('ORVYTH_CLOUD_MAX_TOKENS必须在16到2048之间。')
 payload={'model':model.removeprefix(PREFIX),'messages':messages,'stream':True,'stream_options':{'include_usage':True},'thinking':{'type':'disabled'},'max_tokens':limit}
 request=urllib.request.Request(ENDPOINT,data=json.dumps(payload,ensure_ascii=False).encode('utf8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'text/event-stream'},method='POST')
 try:return CloudResponse(urllib.request.build_opener(NoRedirect()).open(request,timeout=90))
 except urllib.error.HTTPError as error:
  code=error.code;error.close();raise RuntimeError(error_message(code)) from None
 except (OSError,urllib.error.URLError):raise RuntimeError('DeepSeek连接失败或超时，本次未重试，也未切换本地模型。') from None
