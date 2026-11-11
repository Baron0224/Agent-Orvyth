"""口吻层：所有代码模板直出的用户可见回复都从这里出。

规格见同目录 VOICE.md（用户 2026-11-11 定版，锁定；改口吻须用户拍板）。
硬规矩：信息完整性优先于口吻——条件、失败原因、缺失参数、路径与内容一个不许少。
"""
from pathlib import Path
import re

VERSION = 'v1'
SPEC_PATH = Path(__file__).with_name('VOICE.md')


def spec_text():
    try:
        return SPEC_PATH.read_text(encoding='utf-8-sig').strip()
    except OSError:
        return ''


def tidy(text):
    """模型输出兜底：波浪号改成停顿，去掉装饰符号，不碰信息。"""
    text = re.sub(r'[～~]', '，', text)
    text = re.sub(r'[♪✨]', '', text)
    text = re.sub(r'，{2,}', '，', text)
    text = text.replace('，。', '。').replace('。，', '。')
    return text


def call(address=''):
    """句首称呼，保留大小写；没设置就只留空。"""
    name = (address or '').strip()
    return name + '，' if name else ''


# ---------- 提醒 ----------

def condition():
    return '网页开着、别静音，再开一下桌面通知；到点我会弹窗、响一声。'


def daily_note():
    return '每天叫完会自动挪到第二天同一时间，不进“已完成”。'


def capability():
    return ('会的呀。不过有条件：网页得开着，浏览器和系统都别静音；'
            '点“开启桌面通知”，到点我会弹窗、再响一声短提示音。'
            '网页关着不会响，错过的我会标成“已错过”收进已完成。')


def need_time():
    return '这个时间我算不准，给我 1 秒到 24 小时以内的时间，比如“2分钟后”。'


def relative_once():
    return '“几分钟后”这种只能设置一次；想每天，就告诉我每天几点。'


def series_relative_conflict():
    return '你前面选的是连着叫，“几分钟后”只能设置一次。想每天就说每天几点，或者说“取消”重来。'


def interval_unsupported():
    return '我这儿只能设置一天，或者连着每天叫。你说今天还是明天开始、几点，叫一天、几天还是每天。'


def cancelled():
    return '行，这次不设置了。'


def ask_title():
    return '想让我提醒你什么？跟我说一句就行。'


def ask_time(title):
    return f'好，{title}我记下了。想让我几点叫你？比如 13:00。'


def ask_days():
    return '这个要叫几天？一天、连着几天，还是每天都叫？'


def created_once(when, title):
    return f'记好了：{when} 我叫你“{title}”，只提醒一次。{condition()}'


def created_series(start, duration, time, title, daily=False):
    text = f'记好了：从 {start} 开始，{duration} {time} 我叫你“{title}”，已放进右侧待办。{condition()}'
    if daily:
        text += daily_note()
    return text


# ---------- 长期档案 ----------

def fact_saved(saved, total=None, repeated=()):
    """saved: [(label, content)]；repeated: [content]。"""
    lines = ['给你存好了，已存入当前账户的长期档案（只在本机）：']
    lines += [f'- [{label}] {content}' for label, content in saved]
    if total is not None:
        lines.append(f'现在共 {total} 条。')
    if repeated:
        lines.append('这些之前就在档案里，没有重复写入：' + '；'.join(repeated))
    return '\n'.join(lines)


def fact_duplicate(items):
    return '这些之前就存过了，没有重复写入：' + '；'.join(items)


def fact_rejected(items):
    return '这些没有写入长期档案：' + '；'.join(f'{content}（{reason}）' for content, reason in items)


def fact_unreadable(saving=True):
    return '档案这会儿读不出来，这次没有保存。' if saving else '档案这会儿读不出来，这次没法确认。'


def no_password():
    return '档案里没有可用于回答的密码记录，这类凭据我也不会存、不会展示。真要用，请走对应服务的官方入口。'


def fact_answer(label, value, address=''):
    """单条事实的自然说法，标签与值都保留。"""
    head = call(address)
    if label == '姓名':
        return f'{head}你的姓名是{value}。'
    if label == '学校':
        return f'{head}你的学校是{value}。'
    return f'{head}你记的{label}是{value}。'


def fact_answers(pairs, address=''):
    """pairs: [(label, value)]，按自然口吻合成一句话，标签与值都在。"""
    values = dict(pairs)
    parts = []
    if '姓名' in values:
        parts.append('你的姓名是' + values.pop('姓名'))
    if '学校' in values:
        parts.append('学校是' + values.pop('学校'))
    for label, value in values.items():
        parts.append(f'你记的{label}是{value}')
    return f'{call(address)}' + '；'.join(parts) + '。'


def fact_multiple(label, address=''):
    return f'{call(address)}{label}这块档案里有好几条不一样的，我不敢替你挑，你说是哪一条？'


def fact_missing(label, address=''):
    return f'{call(address)}{label}：档案里还没有能确认的记录。'


def listing(items):
    """items: ['[姓名] 我叫穆柏润', ...]"""
    lines = ['我记着这些（只在这台电脑）：']
    lines += [f'{n}. {text}' for n, text in enumerate(items, 1)]
    lines.append('想改就说“修改记忆第1条：新内容”，不要了就说“忘记第1条”。')
    return '\n'.join(lines)


def remembered(content):
    return f'记住了：{content}\n以后新建聊天我会按相关性翻出来看；想改就去设置的记忆管理里改。'


def entry_updated():
    return '改好了。'


def entry_deleted():
    return '已删除这条，我忘掉了。'


def entry_cleared():
    return '已清空长期记忆，都翻篇了。'


def entry_empty():
    return '现在还没有长期记忆。跟我说“记住：……”我就开始记。'


def declaration_name(name):
    return f'好，这轮我就叫你{name}。不过这次还没存进长期档案，没有保存下来；想让我一直记着，就说“记住：{name}”。'


def no_records():
    return '档案里没有找到能确认这条的记录；这不代表之前在本机展示失败过。'


# ---------- 文件 ----------

def file_created(path, content, on_desktop=True):
    where = '已经在桌面创建好了' if on_desktop else '给你建好了'
    return f'{where}：`{path}`，内容我逐字核对过了：\n{content}'


def missing_path():
    return '这个路径我没找到。你把完整路径再发我一次，我照着找。'


def file_exists(name):
    return f'桌面已经有“{name}”了，我没有覆盖；换一个名字我再建。'


def candidates_head():
    return '先按名字找到这些，还没核对内容：'


def ask_index(scope):
    return f'你要哪个？说序号就行。搜索范围：{scope}'


def selected(index):
    return f'好，先记下第 {index} 个；只定位了名字，内容还没读：'


def candidates_again():
    return '候选还在这儿：'


def bad_index():
    return '这个序号不在列表内，挑一个列表里的给我。'


def no_file(fragment, roots):
    return (f'在这些地方按“{fragment}”这个名字片段没找到：{roots}。'
            '搜索受时间、深度、数量和权限限制，别处我不敢说没有；你再给我一个目录？')


def need_name():
    return '还缺文件名，别的我先给你留着。不想一条条报，可以这样说：名字叫你好，内容是我爱你。'


def need_content():
    return '还缺要写的内容。可以这样说：名字叫你好，内容是我爱你。'


def need_dir():
    return '还缺位置：放桌面，还是给我一个文件夹？'


def parse_miss():
    return ' 这次补充我没认出来，可以这样说：名字叫你好，内容是我爱你。'


def send_missing(missing):
    return f'还缺{missing}。收件人信息也得再核对一下；我目前没有发送工具，只能帮你定位和准备，不能替你发出去。'


# ---------- 完成任务 ----------

def task_failed(reason, address=''):
    return f'{call(address)}这次任务未完成——{reason} 我没有重试，也没有覆盖任何文件。'