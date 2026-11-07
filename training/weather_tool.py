"""City-only Open-Meteo current model data, no IP/account geolocation."""
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
TIMEOUT=7
GEO='https://geocoding-api.open-meteo.com/v1/search'
FORECAST='https://api.open-meteo.com/v1/forecast'

def weather_city(text,history,source=None):
    """只接续上一轮天气状态，不从整个聊天或账户推断住址。"""
    source=source or {}
    active=source.get('kind','').startswith('weather')
    weather=bool(re.search(r'天气|气温',text))
    compact=text.strip(' 。！？?!')
    correction=active and bool(re.search(r'下雨|下雪|(?:天气|气温).{0,8}(?:不对|不是|不一样)|^(?:不对|不是这样|不一样)[啊呀吧呢]?[。？！?!]?$|手机.{0,5}(?:晴|阴|雨|雪)',compact))
    place_only=bool(re.fullmatch(r'[\u4e00-\u9fffA-Za-z· ]{2,20}',compact))
    last=history[-1]['content'] if history and history[-1]['role']=='assistant' else ''
    pending=source.get('kind') in ('weather_pending','weather_failure','weather_ambiguous') or '哪座城市' in last
    location_reply=(pending and place_only) or (active and bool(re.fullmatch(r'[\u4e00-\u9fff·]{2,18}[市区县]',compact)))
    if not weather and not correction and not (location_reply and not re.search(r'注册|官网|代码|吃|不查|算了|你好|谢谢|游戏|地图|开心|难受|累|孤独',text)):return None
    known=source.get('query_city','')
    if correction and known:return {'city':known,'district':source.get('district',''),'correction':True}
    city=re.sub(r'截图|今天天气|今天|今日|现在|天气|气温|怎么样|怎样|如何|预报|实时|我想知道|请问|帮我|查一下|查询|的|[？?，,。!！\s]','',text).strip()
    city=re.sub(r'^(我在|城市是|地点是|我)','',city)
    if not city:
        city=known
        # 兼容用户上一句话明确给的位置；不扫描更早的经历。
        if not city and history and history[-1]['role']=='user':
            match=re.fullmatch(r'我在([\u4e00-\u9fffA-Za-z· ]{2,20})',history[-1]['content'])
            if match:city=match.group(1)
    if not city:return {'kind':'weather_pending','answer':'告诉我你想查哪座城市的天气，我帮你看；不用发具体住址。'}
    if len(city)>30 or re.search(r'密码|密钥|账号|邮箱|明天|后天|昨天',city):return {'kind':'weather_pending','answer':'这版能查城市当前时段的天气。先把城市名告诉我，好吗？'}
    district=''
    match=re.fullmatch(r'(.+?市)(.+[区县])',city)
    if match:city,district=match.groups()
    elif city.endswith(('区','县')):
        if known:city,district=known,city
        else:return {'kind':'weather_pending','answer':'这个区县属于哪座城市？补上城市名，我再帮你查，免得找错同名地点。'}
    return {'city':city,'district':district,'correction':False}

def request_json(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Orvyth/0.1 weather'}),timeout=TIMEOUT) as r:return json.load(r)

def current_weather(city,district='',correction=False):
    context={'query_city':city,'district':district}
    try:
        name=city+'市' if re.fullmatch(r'[\u4e00-\u9fff]{2,6}',city) and not city.endswith(('市','区','县')) else city
        geo_url=GEO+'?'+urllib.parse.urlencode({'name':name,'count':5,'language':'zh','format':'json'})
        results=request_json(geo_url).get('results',[])
        if not results and name!=city:
            geo_url=GEO+'?'+urllib.parse.urlencode({'name':city,'count':5,'language':'zh','format':'json'})
            results=request_json(geo_url).get('results',[])
        if not results:return {**context,'answer':'这个地点我还没定位准。补一下完整城市名和省份或国家，我再帮你找。','kind':'weather_failure'}
        administrative=[r for r in results if r.get('feature_code','').startswith('PPLA')]
        candidates=administrative or results
        if len(candidates)!=1:
            options='、'.join(dict.fromkeys(r.get('country','')+r.get('admin1','')+r['name'] for r in candidates))
            return {**context,'answer':'有几个同名地点：'+options+'。你指的是哪一个？我先确认一下，免得给你看错天气。','kind':'weather_ambiguous','locations':candidates}
        place=candidates[0]
        url=FORECAST+'?'+urllib.parse.urlencode({'latitude':place['latitude'],'longitude':place['longitude'],'current':'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m','timezone':'auto','forecast_days':1})
        data=request_json(url);cur=data.get('current',{});units=data.get('current_units',{})
        if not cur.get('time') or cur.get('temperature_2m') is None:raise ValueError('missing current data')
        region=place.get('country','')+place.get('admin1','')+place['name']
        answer=f"我查到{region}当前时段的气温是 {cur['temperature_2m']}{units.get('temperature_2m','')}。"
        for key,label in [('apparent_temperature','体感'),('relative_humidity_2m','相对湿度'),('wind_speed_10m','风速'),('precipitation','模型降水量')]:
            if cur.get(key) is not None:answer+=f"{label} {cur[key]}{units.get(key,'')}；"
        answer=answer.rstrip('；')+'。' if not answer.endswith('。') else answer
        if district:answer+=f'\n你提到的{district}与这座城市的隶属关系和区内天气尚未核实；这里给的是城市坐标数据，不是该区的实测。'
        answer+=f"\n数据时段：{cur['time']}（{data.get('timezone')}，UTC偏移 {data.get('utc_offset_seconds')} 秒）。来源是 Open-Meteo 模型数据，不是气象站实测，也不能代表全天预报或空气质量。"
        if correction:answer='我再按刚才确认的城市查了一次。你看到的天气与这里可能覆盖的地点、时段和来源不同，不能只凭这一份判断你那里有没有下雨。\n'+answer
        return {**context,'kind':'weather','answer':answer,'title':'Open-Meteo current weather','url':url,'geo_url':geo_url,'location':place,'current':cur,'units':units,'timezone':data.get('timezone'),'utc_offset_seconds':data.get('utc_offset_seconds'),'fetched_at':datetime.now().astimezone().isoformat()}
    except (OSError,ValueError,KeyError,TypeError):return {**context,'kind':'weather_failure','answer':'这次天气服务没把数据传回来，我还不能确认天气；先不拿旧数据误导你。'}
