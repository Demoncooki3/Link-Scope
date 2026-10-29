"""Bounded Windows diagnostics. No capture driver needed for Wi-Fi or discovery."""
import concurrent.futures
import ctypes as ct
from ctypes import wintypes as wt
import ipaddress
import json
import locale
import re
import socket
import subprocess
import time
from network_core import CREATE_NO_WINDOW

class IPOptions(ct.Structure):
    _fields_ = [('Ttl',wt.BYTE),('Tos',wt.BYTE),('Flags',wt.BYTE),('OptionsSize',wt.BYTE),('OptionsData',ct.c_void_p)]

class EchoReply(ct.Structure):
    _fields_ = [('Address',wt.DWORD),('Status',wt.DWORD),('RoundTripTime',wt.DWORD),('DataSize',wt.WORD),('Reserved',wt.WORD),('Data',ct.c_void_p),('Options',IPOptions)]

def ip_number(address):
    return int.from_bytes(socket.inet_aton(address),'little')

def ping(address, source, timeout=650):
    """Use the Windows ICMP API: status codes work in every display language."""
    api = ct.WinDLL('iphlpapi.dll')
    api.IcmpCreateFile.restype = wt.HANDLE
    api.IcmpCloseHandle.argtypes = [wt.HANDLE]
    api.IcmpSendEcho2Ex.argtypes = [wt.HANDLE,wt.HANDLE,ct.c_void_p,ct.c_void_p,wt.DWORD,wt.DWORD,ct.c_void_p,wt.WORD,ct.c_void_p,ct.c_void_p,wt.DWORD,wt.DWORD]
    api.IcmpSendEcho2Ex.restype = wt.DWORD
    handle = api.IcmpCreateFile()
    if not handle or handle == ct.c_void_p(-1).value: raise OSError('Cannot open Windows ICMP handle')
    payload = ct.create_string_buffer(b'LinkScope')
    reply = ct.create_string_buffer(ct.sizeof(EchoReply)+len(payload)+32)
    try:
        count = api.IcmpSendEcho2Ex(handle,None,None,None,ip_number(source),ip_number(address),payload,len(payload),None,reply,len(reply),timeout)
        result = EchoReply.from_buffer(reply)
        ok = bool(count and result.Status == 0)
        return {'ok':ok,'ms':int(result.RoundTripTime) if ok else None}
    finally: api.IcmpCloseHandle(handle)

def arp(address, source):
    api = ct.WinDLL('iphlpapi.dll')
    api.SendARP.argtypes = [wt.DWORD,wt.DWORD,ct.c_void_p,ct.POINTER(wt.ULONG)]
    api.SendARP.restype = wt.DWORD
    buf = (ct.c_ubyte * 8)()
    length = wt.ULONG(8)
    code = api.SendARP(ip_number(address),ip_number(source),buf,ct.byref(length))
    if code == 0 and length.value == 6:
        return ':'.join(f'{b:02x}' for b in buf[:6])
    return ''

def scan_network(cidr, address, prefix):
    network = ipaddress.ip_network(cidr.strip(),strict=False)
    local = ipaddress.ip_network(f'{address}/{prefix}',strict=False)
    if network.version != 4 or not network.subnet_of(local):
        raise ValueError('Choose an IPv4 range inside the selected adapter’s subnet.')
    if network.num_addresses > 4096:
        raise ValueError('Choose a /20 or smaller range (at most 4,096 addresses).')
    return network

def resolve_hostname(address):
    reverse=ipaddress.ip_address(address).reverse_pointer
    script="[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; " + f"Resolve-DnsName -Name '{reverse}' -Type PTR -DnsOnly -QuickTimeout -ErrorAction Stop | Where-Object Type -eq PTR | Select-Object -First 1 -ExpandProperty NameHost | ConvertTo-Json -Compress"
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=4,creationflags=CREATE_NO_WINDOW)
        if result.returncode: return ''
        name=json.loads(result.stdout.lstrip('\ufeff'))
        return name.rstrip('.') if isinstance(name,str) else ''
    except (OSError,subprocess.TimeoutExpired,ValueError): return ''

def discover(network, source, local_mac, stop, emit):
    """ARP and ICMP are evidence of discovery, not an exhaustive device inventory."""
    def probe(address):
        ip = str(address)
        if ip == source:
            return {'ip':ip,'mac':local_mac,'ms':0,'method':'Local adapter','hostname':socket.gethostname()}
        mac = arp(ip,source)
        if stop.is_set(): return None
        echo = ping(ip,source)
        if mac or echo['ok']:
            return {'ip':ip,'mac':mac,'ms':echo['ms'],'method':'ARP + ICMP' if mac and echo['ok'] else 'ARP' if mac else 'ICMP','hostname':resolve_hostname(ip) if not stop.is_set() else ''}
        return None
    hosts = iter(network.hosts())
    completed, total = 0, sum(1 for _ in network.hosts())
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        pending = set()
        for _ in range(24):
            address = next(hosts,None)
            if address is not None: pending.add(pool.submit(probe,address))
        while pending:
            done,pending = concurrent.futures.wait(pending,timeout=.2,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                result = future.result()
                completed += 1
                if result: emit('scan_host',result)
                emit('scan_progress',(completed,total))
                if not stop.is_set():
                    address = next(hosts,None)
                    if address is not None: pending.add(pool.submit(probe,address))

def parse_wifi(text):
    """Structured English netsh fields; original output retained for other locales."""
    interfaces, current = [], None
    for line in text.splitlines():
        if ':' not in line: continue
        key,value = (part.strip() for part in line.split(':',1))
        if key == 'Name':
            current = {}; interfaces.append(current)
        if current is not None: current[key] = value
    return interfaces

def parse_access_points(text):
    rows, ssid, auth, current = [], '', '', None
    def make_row():
        return {'ssid':ssid,'bssid':'Not reported','security':auth,'signal':'','channel':'','radio':'','band':''}
    for line in text.splitlines():
        if ':' not in line: continue
        key,value = (part.strip() for part in line.split(':',1))
        if re.fullmatch(r'SSID \d+',key):
            ssid,auth = value or '(hidden)',''
            current=make_row(); rows.append(current)
        elif key == 'Authentication':
            auth = value
            if current is not None: current['security']=value
        elif re.fullmatch(r'BSSID \d+',key):
            if current is None or current['bssid']!='Not reported':
                current=make_row(); rows.append(current)
            current['bssid']=value
        elif current is not None and key in ('Signal','Channel','Radio type','Band'):
            current[{'Signal':'signal','Channel':'channel','Radio type':'radio','Band':'band'}[key]] = value
    return rows

def wireless_snapshot():
    outputs = []
    for args in (['interfaces'],['networks','mode=bssid']):
        result = subprocess.run(['netsh.exe','wlan','show',*args],capture_output=True,text=True,encoding=locale.getpreferredencoding(False),errors='replace',timeout=15,creationflags=CREATE_NO_WINDOW)
        outputs.append(result.stdout + result.stderr)
    return {'interfaces':parse_wifi(outputs[0]),'access_points':parse_access_points(outputs[1]),'raw':'WIRELESS INTERFACES\n'+outputs[0]+'\nNEARBY ACCESS POINTS\n'+outputs[1], 'updated':time.time()}
