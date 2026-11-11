"""Rule-based engine routing for port 8775: pick local or cloud per message.

No model call is made here: routing must be free (no tokens, no latency) and
explainable. The rules are deliberately blunt; when in doubt the answer is
"本机", because the local chain (facts, files, completion checks) already
handles those cases before routing.

Signals that move one message to the cloud engine:
  1. long input      >= 200 characters
  2. code work       写代码 / 改 bug / 看代码 / 代码块 / 函数 / 报错 ...
  3. long generation 写一篇 / 帮我写 / 作文 / 文章 / 方案 / 报告 ...
  4. analysis        分析 / 比较 / 为什么 / 原因 / 规划 / 步骤 / 建议 ...
  5. explicit ask    认真想想 / 仔细点 / 用云端 / 换聪明的 ...
"""
import re

LONG_INPUT = 200

CODE = re.compile(
    r'写(?:个|段|一[段个])?代码|敲代码|改.{0,4}bug|修.{0,4}bug|查.{0,4}bug|看代码|读代码|代码块|'
    r'函数|报错|traceback|stack\s*trace|debug|写个?脚本|爬虫|正则|算法|接口|'
    r'(?i:python|javascript|typescript|sql|api)',
    re.I,
)
GENERATE = re.compile(r'(?:帮|替|请)?我?(?:写|拟|起草|生成|整理|做)(?:一篇|一段|一份|一个|篇|份|段|个)'
                     r'|(?:作文|演讲稿|策划案|文案|周报|月报|总结长文)'
                     r'|(?:写|拟|起草|生成)(?:的)?(?:文章|方案|报告|总结|邮件|简历|稿)')
REASON = re.compile(r'分析|比较|对比|为什么|原因|规划|步骤|建议|怎么做|利弊|评估|推理|原理|优缺点|如何.{0,6}(?:规划|安排|设计)')
EXPLICIT = re.compile(r'认真想|仔细想|想仔细|仔细点|用云端|用deepseek|换聪明|聪明点|深度思考', re.I)

RULES = (
    ('explicit', EXPLICIT, '你要求认真想/用云端'),
    ('long', None, f'输入达到 {LONG_INPUT} 字'),
    ('code', CODE, '代码类问题'),
    ('generate', GENERATE, '长文生成类任务'),
    ('reason', REASON, '需要推理分析'),
)


def choose(question):
    """Return {'engine': 'local'|'deepseek', 'rule': str, 'reason': str}."""
    text = (question or '').strip()
    if not text:
        return {'engine': 'local', 'rule': '', 'reason': ''}
    if EXPLICIT.search(text):
        return {'engine': 'deepseek', 'rule': 'explicit', 'reason': '你要求认真想/用云端'}
    if len(text) >= LONG_INPUT:
        return {'engine': 'deepseek', 'rule': 'long', 'reason': f'输入较长（{len(text)} 字）'}
    if CODE.search(text):
        return {'engine': 'deepseek', 'rule': 'code', 'reason': '代码类问题'}
    if GENERATE.search(text):
        return {'engine': 'deepseek', 'rule': 'generate', 'reason': '长文生成类任务'}
    if REASON.search(text):
        return {'engine': 'deepseek', 'rule': 'reason', 'reason': '需要推理分析'}
    return {'engine': 'local', 'rule': '', 'reason': '简单问题，本机即可'}