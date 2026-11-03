"""Download the official installer; never accept licenses or bypass Windows elevation."""
import hashlib
import os
from pathlib import Path
import tempfile
import time
import urllib.request

VERSION='7.993'
URL=f'https://nmap.org/dist/nmap-{VERSION}-setup.exe'
# Published by https://nmap.org/dist/sigs/nmap-7.993-setup.exe.digest.txt
SHA256='22e5928d1738a1b94ffd3643014f52cb87d467dbec4cff9e5f721fe0b3782f1b'
MAX_BYTES=150*1024*1024

class DownloadCancelled(Exception):
    pass

def download_installer(stop, progress):
    directory=Path(tempfile.mkdtemp(prefix='LinkScope-Nmap-'))
    partial=directory/'installer.part'
    target=directory/f'nmap-{VERSION}-setup.exe'
    digest=hashlib.sha256(); received=0; started=time.monotonic()
    try:
        request=urllib.request.Request(URL,headers={'User-Agent':'LinkScope-Nmap-Installer'})
        with urllib.request.urlopen(request,timeout=20) as response, partial.open('wb') as out:
            if response.geturl()!=URL: raise RuntimeError('Unexpected installer download redirect.')
            total=int(response.headers.get('Content-Length','0'))
            if total>MAX_BYTES: raise RuntimeError('Installer exceeds expected download size.')
            while True:
                if stop.is_set(): raise DownloadCancelled('Download cancelled.')
                if time.monotonic()-started>300: raise TimeoutError('Download exceeded five minutes. Try again.')
                chunk=response.read(256*1024)
                if not chunk: break
                received+=len(chunk)
                if received>MAX_BYTES: raise RuntimeError('Installer exceeds expected download size.')
                out.write(chunk); digest.update(chunk); progress(received,total)
        if stop.is_set(): raise DownloadCancelled('Download cancelled.')
        if total and total!=received: raise RuntimeError('Installer download is incomplete.')
        if digest.hexdigest()!=SHA256: raise RuntimeError('Installer verification failed. It will not be launched.')
        partial.replace(target)
        return str(target)
    except Exception:
        partial.unlink(missing_ok=True)
        directory.rmdir()
        raise

def launch_installer(path):
    # Recheck the exact bytes immediately before requesting the Windows setup UI.
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=SHA256:
        raise RuntimeError('Installer changed after download; refusing to launch.')
    os.startfile(str(Path(path).resolve()),'runas')
