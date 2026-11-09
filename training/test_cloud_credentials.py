"""Dummy credentials only. All disk operations are redirected to a temporary folder."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cloud_credentials as credentials
import cloud_launch as launch


class CredentialsTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_real_dpapi_dummy_roundtrip_damage_and_forget_scope(self):
        with tempfile.TemporaryDirectory() as folder, patch('cloud_credentials.credential_path', return_value=Path(folder)/'deepseek.dpapi'):
            path=credentials.credential_path()
            other=Path(folder)/'other';other.write_text('keep')
            self.assertEqual(credentials.load_key(),'')
            credentials.save_key('dummy-not-real-secret')
            self.assertNotIn(b'dummy-not-real-secret',path.read_bytes())
            self.assertEqual(credentials.load_key(),'dummy-not-real-secret')
            with self.assertRaises(ValueError):credentials.save_key(' ')
            self.assertEqual(credentials.load_key(),'dummy-not-real-secret')
            path.write_bytes(b'damaged')
            with self.assertRaises(OSError):credentials.load_key()
            self.assertEqual(path.read_bytes(),b'damaged')
            credentials.forget_key();self.assertFalse(path.exists());self.assertTrue(other.exists())

    def run_launcher(self, key='', stored='', typed='dummy-key', choice='', args=None, load_error=None, save_error=None):
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':key},clear=True), patch('cloud_launch.load_key',side_effect=load_error,return_value=stored) as load, patch('cloud_launch.save_key',side_effect=save_error) as save, patch('cloud_launch.forget_key') as forget, patch('cloud_launch.sys.stdin.isatty',return_value=True), patch('cloud_launch.getpass.getpass',return_value=typed), patch('builtins.input',side_effect=choice if isinstance(choice,BaseException) else None,return_value=choice if isinstance(choice,str) else '') as prompt, patch('cloud_launch.subprocess.call',return_value=0) as call, contextlib.redirect_stdout(io.StringIO()) as output:
            result=launch.main(args or [])
        return result,load,save,forget,call,output.getvalue()

    def test_env_then_stored_priority(self):
        result,load,save,_,call,output=self.run_launcher(key='dummy-env')
        load.assert_not_called();save.assert_not_called()
        self.assertEqual(call.call_args.kwargs['env']['DEEPSEEK_API_KEY'],'dummy-env')
        self.assertNotIn('dummy-env',str(call.call_args.args)+output)
        _,_,save,_,call,_=self.run_launcher(stored='dummy-stored')
        save.assert_not_called();self.assertEqual(call.call_args.kwargs['env']['DEEPSEEK_API_KEY'],'dummy-stored')

    def test_consent_empty_and_cancel(self):
        for choice,typed,starts,saves in [('', 'dummy-key',True,False),('y','dummy-key',True,True),('c','dummy-key',False,False),('y','',False,False)]:
            with self.subTest(choice=choice,typed=bool(typed)):
                _,_,save,_,call,output=self.run_launcher(typed=typed,choice=choice)
                self.assertEqual(call.called,starts);self.assertEqual(save.called,saves)
                self.assertNotIn('dummy-key',output)
        _,_,save,_,call,_=self.run_launcher(choice=KeyboardInterrupt())
        save.assert_not_called();call.assert_not_called()

    def test_failure_safe_and_forget_confirmation(self):
        _,_,_,forget,call,output=self.run_launcher(load_error=OSError('secret-error'),choice='y',save_error=OSError('secret-error'))
        forget.assert_not_called();self.assertTrue(call.called);self.assertNotIn('secret-error',output)
        for choice,expected in [('',False),('y',True)]:
            _,load,save,forget,call,_=self.run_launcher(choice=choice,args=['--forget-key'])
            self.assertEqual(forget.called,expected);load.assert_not_called();save.assert_not_called();call.assert_not_called()


if __name__=='__main__':unittest.main()
