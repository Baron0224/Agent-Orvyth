"""个人项目按名称只读定位；状态只由当前账户的当前聊天传入。"""
from pathlib import Path
import re
from file_lookup import find_matches, query_name, search_roots, normalize

CONFIRM = r'^(对|是|是的|对是我的资料|是我的资料|对是我的|本地|电脑里|我找不到了你帮我找啊|我找不到了|找不到|帮我找|你帮我找|找一下|好|好的)[啊呀呢吧]*$'

def project_parts(text):
    name=query_name(text)
    english=re.search(r'[A-Za-z][A-Za-z0-9_.-]*(?: +[A-Za-z0-9_.-]+)*',text)
    if english and english.group().lower() not in ('demo',):name=english.group().strip()
    else:
        match=re.search(r'(?:我的|我)([^，。？]{2,40}?)(?:的文件夹|文件夹|的项目|项目|的目录)',text)
        if match:name=match[1].strip('的 ')
    artifact=re.search(r'(?:文件夹|目录|项目)(?:中|里|内)?(?:的)?([^，。？?]+)',text)
    hint=artifact[1].strip() if artifact else ''
    hint=re.split(r'帮我|找一下|找找|大概|主要',hint)[0].strip()
    if not hint:
        hint=next((m.group() for m in re.finditer(r'图纸\s*demo|图纸|demo|原型',text,re.I) if m.group().lower()!=name.lower()),'')
    return name,hint

def locate_project(question, history, context=None):
    context=context or {}
    active=context.get('kind')=='file_lookup'
    last=history[-1].get('content','') if history and history[-1].get('role')=='assistant' else ''
    legacy=any(s in last for s in ('这是你自己的项目资料，对吗','把本地文件夹的完整路径发给我','把网站链接发给我就好'))
    short=re.sub(r'[\s，。？！?!]','',question)
    if re.search(r'算了|先不|不看了|换个话题',question):return None
    if re.search(r'https?://|网站|网页',question):return None
    personal=bool(re.search(r'我.{0,100}(图纸|demo|原型|项目资料)',question,re.I) and re.search(r'查|找|看|读|调取',question))
    local=bool(re.search(r'文件夹|本地|电脑|目录|[A-Za-z]:[\\/]',question))
    confirming=bool(re.fullmatch(CONFIRM,short))
    # 暧昧请求仍先问位置；已明确文件夹，或用户确认个人资料后，使用原有范围。
    if not ((personal and local) or ((active or legacy) and confirming) or (active and re.search(r'[A-Za-z]:[\\/]|^[A-Za-z]盘$',question))):return None
    origin=context.get('request','')
    if not origin:
        origin=question if personal else next((x['content'] for x in reversed(history[-8:]) if x.get('role')=='user' and re.search(r'图纸|demo|原型|项目资料',x.get('content',''),re.I)),question)
    name,hint=project_parts(origin)
    if hint and normalize(name) in normalize(hint) and not re.search(r'(?:的文件夹|的目录|的项目|demo文件夹|图纸文件夹)',origin,re.I):
        state={'kind':'file_lookup','request':origin,'project':'','artifact':hint,'paths':[],'status':'need_name'}
        return {'reply':'我还缺项目或文件夹的名字，只有“'+hint+'”容易混进别的项目。告诉我项目名或要搜索的目录即可，不用先找出文件本身。','file_lookup':state}
    roots=search_roots()
    explicit=re.search(r'["“`]([A-Za-z]:[\\/][^"”`]+)["”`]',question) or re.fullmatch(r'\s*([A-Za-z]:[\\/].+?)\s*',question)
    drive=re.fullmatch(r'([A-Za-z])盘',short)
    if explicit:roots=[Path(explicit[1])]
    elif drive:roots=[Path(drive[1]+':/')]
    if active and not explicit and not drive and context.get('paths'):
        paths=[p for p in context['paths'] if Path(p).exists()]
        if paths:return {'reply':'刚才查到的候选路径如下：\n'+'\n'.join('`'+p+'`' for p in paths)+'\n目前只查了文件和目录名称，没有读取内容，也未确认就是你要的文件。需要看内容时告诉我读取哪一项。','file_lookup':context}
    if active and not explicit and not drive and context.get('scope_requested'):
        return {'reply':'上次按名称搜索还没有找到匹配项目；确认资料是你的，并不能补充搜索范围。你不用先找到文件，只需给一个要查的盘符或目录，例如“D盘”。我会限定范围只读查找。','file_lookup':context}
    state={'kind':'file_lookup','request':origin,'project':name,'artifact':hint,'paths':[]}
    if not roots:return {'reply':'当前没有可用的已配置搜索目录。你只需告诉我要查哪个盘或文件夹，不用先找出完整文件路径。','file_lookup':{**state,'scope_requested':True,'status':'no_scope'}}
    scan=find_matches(name,roots=roots,details=True)
    projects=[p for p in scan['paths'] if p.is_dir()]
    hits=[];partial=False
    if hint:
        for project in projects:
            found=find_matches(hint,roots=[project],details=True)
            hits.extend(found['paths'])
            if found['status']=='limited':scan['status']='limited'
        if not hits:
            # 组合描述未必是完整文件名，例如“图纸demo”；只在已找到项目内按其中名称片段找候选。
            for term in re.findall(r'[A-Za-z][A-Za-z0-9_.-]{2,}',hint):
                if normalize(term)==normalize(hint):continue
                for project in projects:
                    found=find_matches(term,roots=[project],details=True)
                    hits.extend(found['paths'])
                    if found['status']=='limited':scan['status']='limited'
            partial=bool(hits)
    selected=sorted(set(hits or projects),key=str)
    state.update(paths=[str(p) for p in selected],status=scan['status'],roots=scan['roots'],match='approximate' if partial else 'exact' if hits else 'project')
    scope='、'.join(scan['roots'])
    if selected:
        label=('没找到完整名称“'+hint+'”，但找到近似名称候选，尚未确认是不是你要的：') if partial else ('找到名称匹配的图纸/demo候选：' if hits else ('找到项目目录，但没有找到名称匹配的“'+hint+'”：' if hint else '找到项目目录：'))
        return {'reply':label+'\n'+'\n'.join('`'+str(p)+'`' for p in selected[:8])+'\n只检查了名称，未读取文件内容。搜索范围：'+scope+('。本次搜索达到限制或部分目录不可访问，结果可能不全。' if scan['status']=='limited' else '。'),'file_lookup':state}
    state['scope_requested']=True
    limitation='部分目录不可访问或本次搜索达到数量/时间限制，不能断言文件不存在。' if scan['status']=='limited' else '没有找到名称匹配的项目，不代表其他位置没有。'
    return {'reply':'已在这些允许的目录按项目名“'+name+'”查找：'+scope+'。'+limitation+'你只要补充下一步要查哪个盘或目录，不用先找出文件本身。','file_lookup':state}
