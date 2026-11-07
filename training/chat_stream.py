"""增量正文处理：只等待名字、代码标记和URL的最小前缀。"""
import re
from chat_quality import wrong_addressee

class ProseStream:
    def __init__(self):
        self.pending = ''
        self.mode = 'prose'
    def feed(self, text, final=False):
        self.pending += text
        out = []
        while self.pending:
            s = self.pending
            if self.mode == 'url':
                c=s[0];out.append(c);self.pending=s[1:]
                if c.isspace():self.mode='prose'
                continue
            if self.mode in ('prose','fenced') and s[0]=='`':
                if len(s)<3 and all(c=='`' for c in s) and not final:break
                if s.startswith('```'):
                    out.append('```');self.pending=s[3:];self.mode='prose' if self.mode=='fenced' else 'fenced';continue
                if self.mode=='prose':
                    out.append('`');self.pending=s[1:];self.mode='inline';continue
            if self.mode=='inline':
                c=s[0];out.append(c);self.pending=s[1:]
                if c=='`':self.mode='prose'
                continue
            if self.mode=='prose':
                if any(prefix.startswith(s) for prefix in ('https://','http://')) and not final:break
                prefix=next((p for p in ('https://','http://') if s.startswith(p)),None)
                if prefix:out.append(prefix);self.pending=s[len(prefix):];self.mode='url';continue
            if self.mode=='prose' and s[0] in '0123456789#*':
                if not final and (len(s)==1 or (len(s)==2 and s[1]=='\ufe0f')):break
                keycap=re.match(r'^[0-9#*]\ufe0f?\u20e3',s)
                if keycap:self.pending=s[keycap.end():];continue
            c=s[0];self.pending=s[1:]
            n=ord(c)
            if self.mode=='prose' and (0x1F1E6<=n<=0x1FAFF or 0x2600<=n<=0x27BF or n in (0xFE0E,0xFE0F,0x200D,0x20E3) or 0xE0020<=n<=0xE007F):continue
            out.append(c)
        return ''.join(out)

def head_ready(text, assistant_name, address):
    value=text.lstrip()
    if not value:return False
    if '<think>'.startswith(value.lower()) or value.lower().startswith('<think>'):return False
    if address:
        for prefix in (address+'，',address+',',address+'：',address+':'):
            if prefix.startswith(value):return False
            if value.startswith(prefix):value=value[len(prefix):].lstrip();break
    if not value:return False
    if assistant_name.startswith(value):return False
    if value.startswith(assistant_name):
        tail=value[len(assistant_name):].lstrip('，,:： ')
        if not tail or any(greeting.startswith(tail.lower()) for greeting in ('你好','您好','嗨','hi','hello')):return False
    return not wrong_addressee(text,assistant_name,address)

class AddressStream:
    def __init__(self,address):
        self.address=address;self.pending='';self.started=False
    def feed(self,text,final=False):
        if self.started:return text
        self.pending+=text
        value=self.pending.lstrip()
        if not value:return ''
        already_named=False
        if self.address:
            if self.address.startswith(value) and not final:return ''
            match=re.match('^'+re.escape(self.address)+r'[，,:：]\s*',value)
            if match:
                value=value[match.end():]
                if not value and not final:return ''
            elif value==self.address and not final:return ''
            elif value.startswith(self.address):already_named=True
        self.started=True;self.pending=''
        return (self.address+'，' if self.address and not already_named else '')+('\n' if self.address and value.startswith('```') else '')+value
