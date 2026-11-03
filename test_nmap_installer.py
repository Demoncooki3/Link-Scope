import hashlib
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import nmap_installer as installer

class Response(io.BytesIO):
    def __init__(self,data,url=installer.URL):
        super().__init__(data); self.url=url; self.headers={'Content-Length':str(len(data))}
    def geturl(self): return self.url

class InstallerTests(unittest.TestCase):
    def download(self,data,stop=None,url=installer.URL,checksum=None):
        with patch('nmap_installer.urllib.request.urlopen',return_value=Response(data,url)),patch('nmap_installer.SHA256',checksum or hashlib.sha256(data).hexdigest()):
            return installer.download_installer(stop or threading.Event(),lambda *args:None)

    def test_verified_download(self):
        path=Path(self.download(b'installer bytes'))
        try: self.assertEqual(path.read_bytes(),b'installer bytes')
        finally: path.unlink(); path.parent.rmdir()

    def test_mismatch_redirect_cancel(self):
        with self.assertRaisesRegex(RuntimeError,'verification'): self.download(b'bad',checksum='0'*64)
        with self.assertRaisesRegex(RuntimeError,'redirect'): self.download(b'data',url='http://other.test/setup.exe')
        stop=threading.Event(); stop.set()
        with self.assertRaises(installer.DownloadCancelled): self.download(b'data',stop)

    def test_changed_installer_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'setup.exe'; path.write_bytes(b'changed')
            with patch('nmap_installer.os.startfile') as start:
                with self.assertRaises(RuntimeError): installer.launch_installer(path)
                start.assert_not_called()
