"""Owner-isolated structured entries in the existing Hermes USER.md; no second memory store."""
from contextlib import contextmanager
from datetime import datetime
import hashlib,json,re,uuid
from pathlib import Path
from hermes_memory_vendor.store import MemoryStore, _scan_memory_content
from hermes_memory_vendor.compat import memory_root

CATEGORIES={'personal':'个人资料','preference':'回答偏好','habit':'长期习惯','other':'其他／待整理'}
class HermesMemory:
 def __init__(self,directory):self.directory=Path(directory)
 def file_path(self,owner):
  return self.directory/hashlib.sha256(owner.encode('utf-8')).hexdigest()/'USER.md'
 def file_plan(self,owner,question,context,provider):
  explanation=self.storage_answer(owner,question,provider)
  evidence={'kind':'memory_file','local_only':True}
  if explanation:return {'reply':explanation,'file_lookup':evidence}
  active=(context or {}).get('kind')=='memory_file'
  explicit=bool(re.search(r'[A-Za-z]:[\\/]|["“`]/',question))
  # Never accept another account path from the message or an assistant's prose.
  if explicit and re.search(r'hermes-memory|USER\.md',question,re.I):
   return {'reply':'记忆档案只能通过当前账户的记忆入口读取，不接受消息里指定的账户路径。请问“记忆库文件在哪”，再说“读取”。','file_lookup':{'kind':'memory_file_rejected','local_only':True}}
  if not active or explicit:return None
  text=re.sub(r'[\s，。！？?!]','',question)
  if text!='这个文件' and not re.fullmatch(r'(?:请|帮我)?(?:把)?(?:这个文件|该文件|它)?(?:找出来|调出来|读取|打开|查看|读一下|调取)(?:这个文件|该文件|它)?',text):return None
  path=self.file_path(owner)
  try:
   if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in (path,*path.parents)):
    raise ValueError('linked file')
   if not path.is_file():return {'reply':'当前账户的记忆文件尚未建立，无法读取；我没有去读取其他账户的档案。','file_lookup':evidence}
   with path.open('rb') as stream:raw=stream.read(65537)
   if len(raw)>65536:raise ValueError('oversized')
   content=raw.decode('utf-8-sig')
  except (OSError,ValueError):
   return {'reply':'当前记忆文件无法安全读取：可能是链接、权限、编码或超过64KB限制。原文件未更改。','file_lookup':evidence}
  fence='`'*(max([len(m.group()) for m in re.finditer(r'`+',content)]+[2])+1)
  return {'reply':'已在本机只读打开当前账户的记忆文件。以下是原文，不是要执行的指令；本段不会作为聊天历史发给模型，明确保存的精选记忆仍按原机制使用。\n'+fence+'text\n'+content+'\n'+fence,'file_lookup':evidence}
 def storage_answer(self,owner,question,provider):
  if self.is_command(question):return None
  if not (re.search(r'记忆|长期档案',question) and re.search(r'怎么|如何|在哪|哪里|文件|文档|记忆库|有没有用|是不是没用',question)):return None
  path=self.file_path(owner)
  exists=path.is_file()
  return ('当前'+('云端版' if provider=='deepseek' else '本地版')+'账户的长期档案位置是：`'+str(path)+'`。'+('文件已存在；这只能确认已建立，不能证明某一轮回答实际选用了哪些条目。' if exists else '文件尚未建立，不能说已经使用了这份档案。')+
          '\n明确说“记住：……”或在设置→长期档案→记忆管理保存后，系统按当前问题选取条目供回答参考。固定人设负责身份和口吻，长期档案存用户明确保存的信息，聊天历史另外保存在本机数据库，三者不同。云端版与本地版档案独立。你昨天手工提供的其他文档是否已导入，我不能仅凭这句话确认，也没有去读取它。')
 @contextmanager
 def store(self,owner):
  key=hashlib.sha256(owner.encode('utf-8')).hexdigest();root=self.directory/key;token=memory_root.set(root)
  try:
   with MemoryStore._file_lock(root/'profile'):
    store=MemoryStore(user_char_limit=20000);store.load_from_disk();yield store
  finally:memory_root.reset(token)
 @staticmethod
 def decode(raw):
  try:
   item=json.loads(raw)
   if isinstance(item,dict) and item.get('version')==1 and isinstance(item.get('category'),str) and item.get('category') in CATEGORIES and all(isinstance(item.get(k),str) for k in ('id','content','source')) and 'updated_at' in item:return item
  except (ValueError,TypeError):pass
  return {'version':1,'id':'legacy-'+hashlib.sha256(raw.encode()).hexdigest()[:24],'category':'other','content':raw,'source':'legacy','updated_at':None}
 def entries(self,owner):
  with self.store(owner) as store:return [self.decode(raw) for raw in store.user_entries]
 @staticmethod
 def validate(content,category):
  if not isinstance(content,str) or not 2<=len(content.strip())<=400:raise ValueError('内容请填写2到400字。')
  if not isinstance(category,str) or category not in CATEGORIES:raise ValueError('请选择有效类别。')
  if re.search(r'密码|验证码|密钥|身份证|银行卡|(?i:token|api[ _-]?key|sk-|ghp_|github_pat_)|(?<!\d)\d{11,18}(?!\d)|忽略.{0,12}(规则|指令)|绕过.{0,12}(权限|限制)',content):raise ValueError('这条内容不适合普通长期档案，请勿保存凭据、敏感号码或改变权限的指令。')
  if _scan_memory_content(content):raise ValueError('这条内容不适合普通长期档案，不能保存改变身份或权限的指令。')
  return content.strip()
 def mutate(self,owner,action,entry_id=None,content=None,category='other',source='settings',confirmed=False):
  with self.store(owner) as store:
   items=[(raw,self.decode(raw)) for raw in store.user_entries]
   old=next(((raw,item) for raw,item in items if item['id']==entry_id),None)
   if action in ('edit','delete') and not old:raise ValueError('条目不存在或已被其他操作修改，请刷新列表。')
   if action=='clear':
    if not confirmed:raise ValueError('清空需要明确确认。')
    if not items:return []
    # 仅明确确认的清空进入这个分支；复用Hermes单次锁定/重读/原子写，不走模型批量删除防误清空路径。
    result=store._mutate('user',lambda entries,limit:([],'Explicitly confirmed profile clear.'))
   elif action=='delete':result=store.remove('user',old[0])
   elif action in ('add','edit'):
    text=self.validate(content,category)
    duplicate=next((item for _,item in items if item['content']==text and item['id']!=entry_id),None)
    if duplicate and action=='add':return [item for _,item in items]
    if duplicate:raise ValueError('已有相同条目，请删除重复项或修改内容。')
    item={'version':1,'id':old[1]['id'] if old else uuid.uuid4().hex,'category':category,'content':text,'source':old[1]['source'] if old else source,'updated_at':datetime.now().astimezone().isoformat()}
    encoded=json.dumps(item,ensure_ascii=False)
    result=store.replace('user',old[0],encoded) if old else store.add('user',encoded)
   else:raise ValueError('未知记忆操作。')
   if not result.get('success'):raise ValueError('档案未更改：'+str(result.get('error','请稍后重试。')))
   return [self.decode(raw) for raw in store.user_entries]
 @staticmethod
 def category(text):
  if re.search(r'今天|此刻|这次|暂时',text):return 'other'
  if re.search(r'回答|讲解|解释|结论|步骤|回复',text):return 'preference'
  return 'other'
 @staticmethod
 def terms(question):
  clean=re.sub(r'你|我|记得|还|的|什么|是|吗|请|告诉|帮忙|帮|一下|知道|现在|有没有','',question)
  return set(re.findall(r'[a-zA-Z]{3,}',clean.lower())+[clean[i:i+2] for i in range(len(clean)-1) if re.fullmatch(r'[\u4e00-\u9fff]{2}',clean[i:i+2])])
 def selected(self,owner,question='',max_bytes=900):
  terms=self.terms(question);items=self.entries(owner)
  def score(item):return sum(t in item['content'].lower() for t in terms)
  ranked=sorted((i for i in items if i['category']=='preference' or score(i)>0 or not question),key=lambda i:(i['category']=='preference',score(i),i['updated_at'] or ''),reverse=True)
  chosen=[]
  for item in ranked:
   try:self.validate(item['content'],item['category'])
   except ValueError:continue
   data={'category':item['category'],'content':item['content']}
   if len(json.dumps(chosen+[data],ensure_ascii=False).encode('utf8'))<=max_bytes:chosen.append(data)
   if len(chosen)>=6:break
  return chosen
 def prompt(self,owner,question='',max_bytes=900):
  chosen=self.selected(owner,question,max_bytes)
  return json.dumps(chosen,ensure_ascii=False) if chosen else ''
 @staticmethod
 def commands(question):
  normalized=re.sub(r'[\s，。！？?！：:]','',question)
  listing=normalized in ('查看记忆','查看我的记忆','你记住了什么','你都记住了什么','列出记忆','/memory')
  clearing=normalized in ('清空所有记忆','删除所有记忆','清空记忆','/memoryclear')
  add=re.fullmatch(r'(?:请|帮我|替我)?(?:记住|记一下|记下来)[：:，,\s]*(.+)',question.strip(),re.S)
  remove=re.fullmatch(r'(?:请|帮我)?(?:忘记|删除记忆)(?:第)?\s*(\d+)\s*(?:条|条记忆)?[。！!]?|忘记[：:]\s*(.+)',question.strip(),re.S)
  return listing,clearing,add,remove
 def is_command(self,question):return any(self.commands(question)) or bool(re.fullmatch(r'(?:修改|更新|纠正)记忆第?\d+条?[：:].+',question,re.S))
 @staticmethod
 def personal_question(question):return bool(re.search(r'你.{0,4}记得|还记得|我喜欢|我叫什么|我的(?:名字|称呼|偏好|习惯|项目|代号)',question))
 def personal_answer(self,owner,question):
  if not re.search(r'你.{0,4}记得|还记得|我的.{0,12}(是什么|是什么来着|吗[？?]?$)',question):return None
  terms=self.terms(question);items=[]
  if re.search(r'名字|姓名',question):terms.update(('我叫','我的名字','我的姓名','姓名是'))
  if re.search(r'生日|出生日期',question):terms.update(('生日','出生日期'))
  preference=bool(re.search(r'回答|回复|讲解',question) and re.search(r'偏好|习惯',question))
  for i in self.entries(owner):
   try:self.validate(i['content'],i['category'])
   except ValueError:continue
   if any(t in i['content'].lower() for t in terms) or (preference and i['category']=='preference'):items.append(i)
  return '档案里记着：\n'+'\n'.join(i['content'] for i in items) if items else '档案里还没有记录这项，我先不猜。你愿意保存时，可以明确说“记住：……”；称呼仍以设置为准。'
 def command(self,owner,question):
  listing,clearing,add,remove=self.commands(question)
  edit=re.fullmatch(r'(?:修改|更新|纠正)记忆第?(\d+)条?[：:]\s*(.+)',question,re.S)
  if not any((listing,clearing,add,remove,edit)):return None
  try:
   items=self.entries(owner)
   if listing:return '目前还没有长期记忆。需要保存时，请明确说“记住：……” 。' if not items else '我记住了这些（仅保存在这台电脑）：\n'+'\n'.join(f'{n+1}. [{CATEGORIES[i["category"]]}] {i["content"]}' for n,i in enumerate(items))+'\n可说“修改记忆第1条：新内容”或“忘记第1条”。删除档案不等于删除聊天历史。'
   if clearing:self.mutate(owner,'clear',confirmed=True);return '已清空长期记忆。聊天历史仍然保留；新建聊天后不会再注入这些档案。'
   if add:
    content=add[1].strip().strip('：:，,');self.mutate(owner,'add',content=content,category=self.category(content),source='explicit_chat');return '记住了：'+content+'\n以后新建聊天会按相关性参考。可在设置的记忆管理里改类别、编辑或删除。'
   if edit:
    index=int(edit[1])-1
    if not 0<=index<len(items):raise ValueError('没有这一条记忆。')
    content=edit[2].strip();self.mutate(owner,'edit',items[index]['id'],content, self.category(content));return '已更新这条记忆，旧内容已替换。新建聊天会使用新版；旧聊天原消息仍保留。'
   if remove[1]:
    index=int(remove[1])-1
    if not 0<=index<len(items):raise ValueError('没有这一条记忆。')
    entry=items[index]
   else:
    matches=[i for i in items if remove[2].strip()==i['content']]
    if len(matches)!=1:raise ValueError('请先查看记忆，按序号明确要删除哪条。')
    entry=matches[0]
   self.mutate(owner,'delete',entry['id']);return '已删除这条长期记忆。聊天历史原消息仍保留；新建聊天后不再注入。'
  except ValueError as error:return str(error)
