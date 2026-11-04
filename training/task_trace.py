"""Evidence from actual tool execution, independent of model claims."""
from pathlib import Path

class TaskTrace:
    def __init__(self, emit):
        self.data={'state':'running','steps':[]}
        self.emit=emit
        self.step('正在处理任务')

    def step(self,label,path=''):
        self.data['steps'].append({'label':label,'path':path})
        self.emit({'type':'task','task':self.data})

    def finish(self,state,label):
        self.data['state']=state
        self.step(label)

    def tool(self,event,folder):
        names={'read_project':'已读取文件','list_project':'已查看目录','replace_word_text':'已保存并验证 Word 副本'}
        name=event.get('name')
        if name not in names:return
        root=Path(folder).resolve()
        target=(root/event.get('path','')).resolve()
        target.relative_to(root)
        if not target.exists():raise RuntimeError('工具报告的文件或目录不存在，无法确认任务完成。')
        if name=='replace_word_text' and (not target.is_file() or not target.stat().st_size):
            raise RuntimeError('生成的文件为空，无法确认任务完成。')
        self.step(names[name],str(target))
