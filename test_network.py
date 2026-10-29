import unittest
from network_core import decode_lldp, subnet, inventory, cable_assessment

def tlv(kind, value):
    return ((kind << 9) | len(value)).to_bytes(2,'big') + value

def frame(ttl=120):
    return bytes.fromhex('0180c200000e00112233445588cc') + b''.join([
        tlv(1,b'\x04\x00\x11\x22\x33\x44\x55'),tlv(2,b'\x05Gi1/0/24'),
        tlv(3,ttl.to_bytes(2,'big')),tlv(5,b'Lab Switch'),
        tlv(8,b'\x05\x01\xc0\xa8\x01\x01\x02\x00\x00\x00\x01\x00'),
        tlv(127,b'\x00\x80\xc2\x01\x00\x64'),tlv(0,b'')])

class CoreTests(unittest.TestCase):
    def test_physical_cable_evidence(self):
        a={'hardware':True,'interface_type':6,'status':'Up','media_state':'Connected','speed':'1 Gbps'}
        self.assertEqual(cable_assessment(a)['powered_peer'],'Active link partner detected')
        self.assertIn('Not measured',cable_assessment(a)['continuity'])
        for changes in ({'interface_type':71},{'hardware':False},{'status':'Disabled'},{'status':'Disconnected'},{'media_state':'Unknown'}):
            self.assertEqual(cable_assessment({**a,**changes})['powered_peer'],'Unknown')

    def test_advertisement(self):
        n = decode_lldp(frame())
        self.assertEqual((n['system_name'],n['port'],n['vlan']),('Lab Switch','Gi1/0/24','100'))
        self.assertEqual(n['management'],['192.168.1.1'])
        self.assertEqual(n['chassis'],'00:11:22:33:44:55')

    def test_tagged(self):
        f = frame()
        self.assertEqual(decode_lldp(f[:12]+bytes.fromhex('8100006488cc')+f[14:])['ttl'],120)

    def test_shutdown(self):
        self.assertEqual(decode_lldp(frame(0))['ttl'],0)

    def test_malformed(self):
        with self.assertRaises(ValueError): decode_lldp(frame()[:-3])
        self.assertIsNone(decode_lldp(b'hello'))
        self.assertIsNone(decode_lldp(bytes(60)))

    def test_subnets(self):
        self.assertEqual(subnet('192.168.12.8',24)['network'],'192.168.12.0/24')
        self.assertEqual(subnet('10.0.0.0',31)['hosts'],2)
        self.assertEqual(subnet('10.0.0.1',32)['first'],'10.0.0.1')

if __name__ == '__main__': unittest.main()
