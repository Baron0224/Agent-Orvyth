"""Evidence from actual tool execution, independent of model claims."""
import re
from pathlib import Path

FAILURE_CLAIMS = re.compile(r'无法读取|读不到|打不开|读取失败|没有权限|无权限|无法访问|访问不了|没找到这个文件|文件不存在')
READ_CLAIMS = re.compile(r'已读取|读到了|读取成功|我已经读|读完了')
MAX_EVIDENCE = 12000


def quote(text):
    fence = '````' if '```' in text else '```'
    return f'{fence}\n{text}\n{fence}'


class TaskTrace:
    def __init__(self, emit):
        self.data = {'state': 'running', 'steps': [], 'tools': []}
        self.emit = emit
        self.step('正在处理任务')

    def step(self, label, path=''):
        self.data['steps'].append({'label': label, 'path': path})
        self.emit({'type': 'task', 'task': self.data})

    def finish(self, state, label):
        self.data['state'] = state
        self.step(label)

    def tool(self, event, folder):
        names = {'read_project': '已读取文件', 'list_project': '已查看目录', 'replace_word_text': '已保存并验证 Word 副本'}
        name = event.get('name')
        if name not in names:
            return
        root = Path(folder).resolve()
        target = (root / event.get('path', '')).resolve()
        target.relative_to(root)
        if not target.exists():
            raise RuntimeError('工具报告的文件或目录不存在，无法确认任务完成。')
        if name == 'replace_word_text' and (not target.is_file() or not target.stat().st_size):
            raise RuntimeError('生成的文件为空，无法确认任务完成。')
        self.data['tools'].append({'name': name, 'path': str(target)})
        self.step(names[name], str(target))

    def reads(self):
        return [item for item in self.data['tools'] if item['name'] == 'read_project']

    def reconcile(self, answer, only_file=None):
        """Refuse to call a task complete when the reply contradicts the tool record."""
        reads = self.reads()
        if only_file and not reads:
            raise RuntimeError(f'任务要求读取「{only_file}」，但工具记录里没有成功读取它的记录，不能确认任务完成。')
        if not reads and READ_CLAIMS.search(answer):
            raise RuntimeError('最终回答称已经读取文件，但工具记录里没有读取成功的记录，不能确认任务完成。')
        if reads and FAILURE_CLAIMS.search(answer):
            target = Path(reads[0]['path'])
            try:
                text = target.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                raise RuntimeError('工具记录显示已读取文件，但最终回答称无法读取，两者不一致，不能确认任务完成。')
            if len(text) > MAX_EVIDENCE:
                raise RuntimeError('工具记录显示已读取文件，但最终回答称无法读取，且文件内容过长无法逐字核对，不能确认任务完成。')
            self.step('最终回答与读取记录不一致，已改用工具实际读取的内容')
            return f'已读取文件：`{target}`\n\n{quote(text.strip() or "（文件是空的）")}'
        return answer