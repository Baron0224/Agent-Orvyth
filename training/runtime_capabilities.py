"""当前服务的能力自评；只报告注册和检测结果，不冒充任务执行。"""
import re

EXTERNAL = r'外部|插件|github|开源|最新|新方案|网上|网页|第三方|搜索.{0,8}(工具|方案)|联网.{0,8}(方案|工具)'

def is_self_assessment(text):
    external_text=re.sub(r'orvyth','',text,flags=re.I)
    if re.search(EXTERNAL,external_text,re.I) or re.search(r'[A-Za-z][A-Za-z0-9.+-]{1,}',external_text):return False
    if re.search(r'你.{0,6}(帮我|帮忙|替我).{0,20}(优化|完善|改进)',text):return False
    return bool(re.search(r'你|自己|自身|orvyth',text,re.I) and re.search(r'能力|功能|不足|局限|限制|改进|优化|完善|需要补充|还需要|能做什么',text))

def assessment(snapshot):
    status=snapshot['status']
    model=status.get('model','未确认')
    lines=['作为你的私人AI秘书，我先按当前配置帮你理清范围。这次只核对配置和工具状态，没有查看日志、扫描电脑或修改程序。']
    lines.append('当前聊天模型：'+model+'；'+(status['message'] if status.get('provider') == 'deepseek' else ('模型已安装，尚未做本轮生成质量测试。' if status.get('ready') else '聊天服务未就绪或模型未安装，先恢复连接再谈增加功能。')))
    lines.append('已接入：'+ '、'.join(snapshot['registered'])+'。这些入口已接入不代表本轮外部服务调用成功。')
    lines.append('文件工具：'+('Pi依赖和工具模型已安装；尚未实际读取文件验证。' if snapshot['pi_ready'] else 'Pi依赖或工具模型未就绪，目前不能保证文件内容读取/Word工具能执行。'))
    lines.append('使用范围：联网搜索、天气服务本轮未测连通；新闻只用BBC公开源，不能当完整的国内新闻；天气只提供城市坐标模型数据，不能当区内实测。文件名称查找有限时和范围，近似候选不等于内容确认。')
    lines.append('接下来我建议先做两件事：一是让资料来源、日期和失败原因更容易核对，二是为文件查找和多轮补充建立固定的实际验收案例。先把已有能力做可靠，再考虑加功能。这是建议，还没有执行。')
    return '\n\n'.join(lines)
