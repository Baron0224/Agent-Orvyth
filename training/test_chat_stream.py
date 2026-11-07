import io,json,unittest
from unittest.mock import patch
from chat_stream import ProseStream,AddressStream,head_ready
from chat_local import LocalChat
class StreamTests(unittest.TestCase):
    def test_leading_address_without_comma_is_not_duplicated(self):
        stream=AddressStream('爸爸');out=''
        for part in ('爸','爸','今天','开心'):out+=stream.feed(part)
        out+=stream.feed('',final=True)
        self.assertEqual(out,'爸爸今天开心')
    def test_prefixes_and_unicode_code_url_survive_arbitrary_splits(self):
        raw='爸爸，中文😊。\n```python\nprint("😊")\n```\n`😊` https://x.test/😊'
        prose=ProseStream();address=AddressStream('爸爸');out=''
        for char in raw:out+=address.feed(prose.feed(char))
        out+=address.feed(prose.feed('',final=True));out+=address.feed('',final=True)
        self.assertEqual(out,'爸爸，中文。\n```python\nprint("😊")\n```\n`😊` https://x.test/😊')
    def test_keycaps_one_character_at_a_time(self):
        stream=ProseStream();raw='1️⃣2⃣👩‍💻123 1.2 `1️⃣` https://x.test/1️⃣'
        out=''.join(stream.feed(c) for c in raw)+stream.feed('',final=True)
        self.assertEqual(out,'123 1.2 `1️⃣` https://x.test/1️⃣')
    def test_header_guard_delays_wrong_role_and_legacy_reasoning(self):
        for text in ('爸','爸爸，','爸爸，小白','爸爸，小白你好呀！','<thi','<think>secret'):
            self.assertFalse(head_ready(text,'小白','爸爸'))
        self.assertTrue(head_ready('爸爸，先运行','小白','爸爸'))
    def test_qwen_yields_before_done_is_consumed(self):
        chunks=[{'message':{'content':'先'}},{'message':{'content':'学print(1)。😊'}},{'done':True}]
        class Response:
            read_count=0
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def __iter__(self):
                for chunk in chunks:
                    self.read_count+=1;yield (json.dumps(chunk)+'\n').encode()
        response=Response();chat=LocalChat('qwen3:8b')
        with patch('chat_local.urllib.request.build_opener') as build:
            build.return_value.open.return_value=response;stream=chat.reply('教我print')
            first=next(stream);self.assertEqual(first,'先');self.assertEqual(response.read_count,1)
            full=first+''.join(stream)
        self.assertEqual(full,'先学print(1)。');self.assertEqual(chat.history[-1]['content'],full)
    def test_split_think_never_streams(self):
        chunks=[{'message':{'content':part}} for part in ('<thi','nk>secret','</think>正文')]+[{'done':True}]
        raw=b''.join((json.dumps(x)+'\n').encode() for x in chunks)
        with patch('chat_local.urllib.request.build_opener') as build:
            build.return_value.open.return_value=io.BytesIO(raw)
            self.assertEqual(''.join(LocalChat('qwen3:8b').reply('解释概念')),'正文')
if __name__=='__main__':unittest.main()
