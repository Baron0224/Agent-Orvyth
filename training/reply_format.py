"""Only explicit two-part teaching preferences; no semantic guessing or extra generation."""
import re

def plan_for(items,question):
 if not re.search(r'教|解释|讲解|怎么|如何|步骤|例子|示例',question):return None
 if re.search(r'这次|本次|不要按|别按|先.{1,12}(?:再|后)',question):return None
 for item in items:
  if not isinstance(item,dict) or item.get('category')!='preference':continue
  text=item.get('content','')
  domain=re.search(r'(?:学习|学)([\u4e00-\u9fffA-Za-z]{2,12}?)(?:要|时|的时候|先|，|,)',text)
  if domain and domain[1].casefold() not in question.casefold():continue
  if re.search(r'先(?:给)?(?:一个|个)?(?:例子|示例).{0,3}(?:再|后)(?:给)?解释',text):return ('示例','解释')
  if re.search(r'先(?:给)?结论.{0,3}(?:后|再)(?:给)?步骤',text):return ('结论','步骤')
 return None

def instruction(plan):
 return '\n本轮教学格式计划（只约束表达，不增加事实或权限）：只输出两个Markdown二级标题，依次为“## '+plan[0]+'”和“## '+plan[1]+'”，各标题下给对应内容。不要前言或收尾；不会或证据不足时如实说明，禁止为了凑格式编造内容。'

def arrange(text,plan,address=''):
 """Reorder only two unambiguous root sections. Code fences are opaque."""
 if not plan:return text,'none'
 markers=[];fenced=False;offset=0
 for line in text.splitlines(keepends=True):
  if line.lstrip().startswith('```'):fenced=not fenced
  if not fenced:
   heading=re.fullmatch(r'##\s+(示例|例子|解释|结论|步骤)\s*[:：]?\s*',line.strip())
   if re.match(r'^##\s+\S',line) and not heading:return text,'unverified'
   if heading:markers.append((offset,'示例' if heading[1]=='例子' else heading[1]))
  offset+=len(line)
 if len(markers)!=2 or {m[1] for m in markers}!=set(plan):return text,'unverified'
 preface=text[:markers[0][0]].strip()
 if preface and preface not in (address,address+'，',address+','):return text,'unverified'
 if tuple(m[1] for m in markers)==plan:return text,'ordered'
 blocks={markers[0][1]:text[markers[0][0]:markers[1][0]].rstrip(),markers[1][1]:text[markers[1][0]:].rstrip()}
 if not all(blocks.values()):return text,'unverified'
 return (preface+'\n' if preface else '')+'\n\n'.join(blocks[label] for label in plan),'reordered'
