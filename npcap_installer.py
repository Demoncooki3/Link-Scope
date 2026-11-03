"""Npcap prerequisites for the bundled Scapy LLDP listener."""
import os
from pathlib import Path
import subprocess
from network_core import CREATE_NO_WINDOW
from nmap_installer import download_installer, launch_installer

VERSION='1.90'
URL='https://npcap.com/dist/npcap-1.90.exe'
# Official HTTPS download, Authenticode verified: Nmap Software LLC.
SHA256='682b57e1c05ef375931975c9d6ded40888f4bfdf9f4b11571e654f962f1199b6'

def download_npcap(stop,progress):
    return download_installer(stop,progress,url=URL,checksum=SHA256,filename=f'npcap-{VERSION}.exe')

def launch_npcap(path):
    launch_installer(path,checksum=SHA256)

def npcap_installed():
    dll=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'/'Npcap'/'wpcap.dll'
    if not dll.is_file(): return False
    result=subprocess.run(['sc.exe','query','npcap'],capture_output=True,timeout=5,creationflags=CREATE_NO_WINDOW)
    return result.returncode==0
