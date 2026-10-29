"""Windows inventory and defensive LLDP decoding, independent of the GUI."""
import ipaddress
import json
import subprocess

CREATE_NO_WINDOW = 0x08000000

def inventory():
    script = r'''
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$adapters = @(Get-NetAdapter | ForEach-Object {
 $a = $_
 $c = Get-NetIPConfiguration -InterfaceIndex $a.ifIndex -ErrorAction SilentlyContinue
 $v4 = @(Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object { @{address=$_.IPAddress; prefix=$_.PrefixLength} })
 $v6 = @(Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv6 -ErrorAction SilentlyContinue | ForEach-Object { $_.IPAddress })
 @{ name=$a.Name; description=$a.InterfaceDescription; index=$a.ifIndex; guid="$($a.InterfaceGuid)"; status="$($a.Status)"; mac=$a.MacAddress; speed=$a.LinkSpeed; hardware=[bool]$a.HardwareInterface; interface_type=[int]$a.InterfaceType; media_state="$($a.MediaConnectionState)"; ipv4=$v4; ipv6=$v6; gateway=@($c.IPv4DefaultGateway.NextHop); dns=@($c.DNSServer.ServerAddresses) }
})
ConvertTo-Json -InputObject $adapters -Depth 6 -Compress
'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=35, creationflags=CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Unable to read Windows adapters')
    return json.loads(result.stdout.lstrip('\ufeff'))

def subnet(address, prefix):
    net = ipaddress.ip_network(f'{address}/{prefix}', strict=False)
    return {'network': str(net), 'mask': str(net.netmask), 'broadcast': str(net.broadcast_address), 'first': str(net.network_address + (1 if net.prefixlen < 31 else 0)), 'last': str(net.broadcast_address - (1 if net.prefixlen < 31 else 0)), 'hosts': net.num_addresses - (2 if net.prefixlen < 31 else 0)}

def cable_assessment(adapter):
    result = {'continuity':'Not measured — requires cable diagnostic hardware', 'powered_peer':'Unknown', 'speed':'Unknown'}
    if not adapter or not adapter.get('hardware') or adapter.get('interface_type') != 6:
        result.update(state='Select a physical Ethernet adapter', detail='Wi-Fi, VPNs, and virtual adapters cannot provide Ethernet cable link evidence.')
    elif adapter.get('status') == 'Up' and adapter.get('media_state') == 'Connected':
        result.update(state='Active Ethernet link', powered_peer='Active link partner detected', speed=adapter.get('speed','Unknown'), detail='The adapter reports an established Ethernet link. This indicates an active remote Ethernet transceiver. It does not identify the device as a switch, prove the whole device is booted, or certify every wire pair.')
    elif adapter.get('status') in ('Disconnected','Down'):
        result.update(state='No Ethernet link detected',detail='Possible causes include an unplugged or faulty cable, a powered-off remote device, a disabled remote port, or negotiation problems. Windows cannot distinguish these from link state alone.')
    else:
        result.update(state='Adapter unavailable or link state unknown',detail='Check that the physical Ethernet adapter is enabled, present, and has a working driver. No conclusion about cable continuity or remote device power is possible.')
    return result

def _identifier(value, mac_kind):
    if not value:
        return ''
    kind, data = value[0], value[1:]
    if kind == mac_kind and len(data) == 6:
        return ':'.join(f'{b:02x}' for b in data)
    return data.decode('utf-8', errors='replace').strip('\x00')

def decode_lldp(frame):
    if len(frame) < 14:
        return None
    offset, ethertype = 14, int.from_bytes(frame[12:14], 'big')
    while ethertype in (0x8100, 0x88a8):
        if len(frame) < offset + 4:
            return None
        ethertype = int.from_bytes(frame[offset+2:offset+4], 'big')
        offset += 4
    if ethertype != 0x88cc:
        return None
    item = {'source_mac': ':'.join(f'{b:02x}' for b in frame[6:12]), 'chassis': '', 'port': '', 'ttl': None, 'system_name': '', 'description': '', 'port_description': '', 'management': [], 'vlan': '', 'capabilities': ''}
    ended = False
    while offset + 2 <= len(frame):
        header = int.from_bytes(frame[offset:offset+2], 'big')
        kind, size = header >> 9, header & 511
        offset += 2
        if offset + size > len(frame):
            raise ValueError('Truncated LLDP TLV')
        value = frame[offset:offset+size]
        offset += size
        if kind == 0:
            ended = True
            break
        if kind == 1:
            item['chassis'] = _identifier(value, 4)
        elif kind == 2:
            item['port'] = _identifier(value, 3)
        elif kind == 3 and size == 2:
            item['ttl'] = int.from_bytes(value, 'big')
        elif kind in (4, 5, 6):
            item[{4:'port_description',5:'system_name',6:'description'}[kind]] = value.decode('utf-8', errors='replace').strip('\x00')
        elif kind == 7 and size >= 4:
            enabled = int.from_bytes(value[2:4], 'big')
            item['capabilities'] = ', '.join(name for bit, name in [(1,'Repeater'),(2,'Bridge'),(3,'WLAN'),(4,'Router'),(5,'Telephone'),(7,'Station')] if enabled & (1 << bit))
        elif kind == 8 and size >= 2:
            length = value[0]
            if length > 1 and len(value) >= length + 1:
                data = value[2:1+length]
                if (value[1] == 1 and len(data) == 4) or (value[1] == 2 and len(data) == 16):
                    item['management'].append(str(ipaddress.ip_address(data)))
        elif kind == 127 and size >= 6 and value[:4] == b'\x00\x80\xc2\x01':
            item['vlan'] = str(int.from_bytes(value[4:6], 'big'))
    if not ended or not item['chassis'] or not item['port'] or item['ttl'] is None:
        raise ValueError('Incomplete LLDP advertisement')
    return item
