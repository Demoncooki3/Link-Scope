import subprocess
import sys
import threading
import unittest
from external_tools import validate_target, trace_command, nmap_command, run_command

class ExternalToolsTests(unittest.TestCase):
    def test_targets_and_options(self):
        for value in ('-oN output.txt','host & whoami','host;echo','http://example.com','192.168.1.1 192.168.1.2','::1'):
            with self.assertRaises(ValueError): validate_target(value)
        self.assertEqual(trace_command(' example.com ')[-1],'example.com')
        with self.assertRaises(ValueError): trace_command('192.168.1.0/24')
        with self.assertRaises(ValueError): nmap_command('nmap.exe','10.0.0.0/16','Host discovery')
        with self.assertRaises(ValueError): nmap_command('nmap.exe','10.0.0.0/23','Service detection')
        command=nmap_command('nmap.exe','192.168.1.1','TCP top 100 ports')
        self.assertIn('-sT',command)
        self.assertNotIn('-sV',command)
        self.assertIn('-sV',nmap_command('nmap.exe','192.168.1.1','Service detection'))

    def test_process_output_failure_and_cancellation(self):
        stop=threading.Event()
        result=run_command([sys.executable,'-c','print("result")'],stop,5)
        self.assertEqual(result['state'],'completed'); self.assertIn('result',result['output'])
        result=run_command([sys.executable,'-c','raise SystemExit(3)'],stop,5)
        self.assertEqual(result['state'],'failed')
        stop.set()
        result=run_command([sys.executable,'-c','import time; time.sleep(30)'],stop,5)
        self.assertEqual(result['state'],'cancelled'); self.assertLess(result['duration_seconds'],3)

    def test_process_deadline(self):
        result=run_command([sys.executable,'-c','import time; time.sleep(30)'],threading.Event(),.1)
        self.assertEqual(result['state'],'timed out')
