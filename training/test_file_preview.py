import unittest,tempfile,os,json
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import test_chat_web
class PreviewTest(unittest.TestCase):
 def test_authorization_and_image_boundaries(self):
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   root=Path(web.directory.name);image=root/'图纸demo.png';Image.new('RGB',(40,20),'#d6e5ef').save(image)
   owner=web.server.store.key(web.cookie.split('=',1)[1]);evidence={'kind':'file_lookup','paths':[str(image)],'roots':[str(root)],'match':'approximate'}
   web.server.store.save_pair(owner,web.chat,'找图','候选',search_evidence=evidence)
   state=web.state();card=state['messages'][-1]['file_results'][0];url=card['preview_url']
   with patch.dict(os.environ,{'ORVYTH_FILE_ROOTS':str(root)}):
    import http.client
    def fetch(url,cookie):
     c=http.client.HTTPConnection('127.0.0.1',web.server.server_port);c.request('GET',url,headers={'Cookie':cookie});r=c.getresponse();data=r.read();status=r.status;c.close();return status,data
    status,data=fetch(url,web.cookie);self.assertEqual(status,200);self.assertTrue(data.startswith(b'\x89PNG'))
    self.assertEqual(fetch(url,'')[0],403)
    _,headers,other=web.request('GET','/api/session',extra={'Cookie':''});self.assertEqual(fetch(url,headers['Set-Cookie'].split(';')[0])[0],403)
    self.assertEqual(fetch(url.replace('index=0','index=99'),web.cookie)[0],403)
    from file_preview import preview,MAX_BYTES
    image.write_bytes(b'x'*(MAX_BYTES+1));self.assertEqual(fetch(url,web.cookie)[0],403)
    traversal=root/'sub'/'..'/'图纸demo.png'
    with self.assertRaises(ValueError):preview(traversal,evidence)
    link=root/'link.png'
    try:link.symlink_to(image)
    except OSError:pass
    else:
     with self.assertRaises(ValueError):preview(link,evidence)
    image.write_text('<svg onload="alert(1)">');self.assertEqual(fetch(url,web.cookie)[0],403)
   with patch.dict(os.environ,{'ORVYTH_FILE_ROOTS':str(root/'outside')}):self.assertEqual(fetch(url,web.cookie)[0],403)
  finally:web.tearDown()
if __name__=='__main__':unittest.main()
