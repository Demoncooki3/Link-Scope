"""Validated command arguments and cancellable external diagnostic processes."""
import ipaddress
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from network_core import CREATE_NO_WINDOW

PROFILES = ('Host discovery', 'TCP top 100 ports', 'Service detection')

def validate_target(value, allow_network=False, limit=4096):
    value=value.strip()
    if '/' in value:
        if not allow_network: raise ValueError('Enter one IPv4 address or hostname.')
        try: net=ipaddress.ip_network(value,strict=False)
        except ValueError: raise ValueError('Enter a valid IPv4 CIDR range.') from None
        if net.version!=4 or net.num_addresses>limit: raise ValueError(f'Use an IPv4 range with at most {limit} addresses.')
        return str(net)
    try:
        ip=ipaddress.ip_address(value)
        if ip.version!=4: raise ValueError('This diagnostic supports IPv4 targets.')
        return str(ip)
    except ValueError:
        if ':' in value: raise ValueError('This diagnostic supports IPv4 targets.') from None
    if len(value)>253 or not value or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',part) for part in value.rstrip('.').split('.')):
        raise ValueError('Enter one hostname, IPv4 address, or supported IPv4 CIDR range; command options are not accepted.')
    return value

def find_nmap():
    path=shutil.which('nmap.exe')
    if path: return path
    for root in (os.environ.get('ProgramFiles',''),os.environ.get('ProgramFiles(x86)','')):
        if root and (Path(root)/'Nmap'/'nmap.exe').is_file(): return str(Path(root)/'Nmap'/'nmap.exe')
    return ''

def nmap_command(executable,target,profile):
    if profile not in PROFILES: raise ValueError('Select an Nmap profile.')
    target=validate_target(target,True,4096 if profile==PROFILES[0] else 256)
    flags=['-sn'] if profile==PROFILES[0] else ['-sT','-Pn','--top-ports','100']
    if profile==PROFILES[2]: flags+=['-sV','--version-light']
    return [executable,*flags,'--host-timeout','45s','--max-retries','1',target]

def trace_command(target):
    return ['tracert.exe','-4','-d','-h','30','-w','1000',validate_target(target)]

def run_command(command,stop,timeout):
    started=time.monotonic()
    with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',creationflags=CREATE_NO_WINDOW) as process:
        state='completed'
        while True:
            try:
                output,_=process.communicate(timeout=.2)
                break
            except subprocess.TimeoutExpired:
                if stop.is_set() or time.monotonic()-started>=timeout:
                    state='cancelled' if stop.is_set() else 'timed out'
                    process.kill()
                    output,_=process.communicate()
                    break
        if state=='completed' and process.returncode: state='failed'
        return {'state':state,'returncode':process.returncode,'command':command,'output':output[-200000:],'duration_seconds':round(time.monotonic()-started,2)}
