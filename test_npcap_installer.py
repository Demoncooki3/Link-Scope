import unittest
from unittest.mock import patch, Mock
import npcap_installer as npc

class NpcapInstallerTests(unittest.TestCase):
    def test_missing_library(self):
        with patch('npcap_installer.Path.is_file',return_value=False),patch('npcap_installer.subprocess.run') as run:
            self.assertFalse(npc.npcap_installed()); run.assert_not_called()

    def test_driver_required(self):
        with patch('npcap_installer.Path.is_file',return_value=True),patch('npcap_installer.subprocess.run',return_value=Mock(returncode=0)):
            self.assertTrue(npc.npcap_installed())
        with patch('npcap_installer.Path.is_file',return_value=True),patch('npcap_installer.subprocess.run',return_value=Mock(returncode=1060)):
            self.assertFalse(npc.npcap_installed())

    def test_npcap_checksum_used(self):
        with patch('npcap_installer.download_installer',return_value='setup.exe') as download:
            self.assertEqual(npc.download_npcap(None,None),'setup.exe')
            self.assertEqual(download.call_args.kwargs['checksum'],npc.SHA256)
            self.assertEqual(download.call_args.kwargs['url'],npc.URL)
        with patch('npcap_installer.launch_installer') as launch:
            npc.launch_npcap('setup.exe')
            self.assertEqual(launch.call_args.kwargs['checksum'],npc.SHA256)
