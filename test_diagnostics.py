import ipaddress
import threading
import unittest
from unittest.mock import patch
from diagnostics import scan_network, discover, parse_wifi, parse_access_points

class DiagnosticsTests(unittest.TestCase):
    def test_range_validation(self):
        self.assertEqual(str(scan_network('192.168.4.16/28','192.168.4.40',24)),'192.168.4.16/28')
        for cidr in ['192.168.5.0/24','0.0.0.0/0','::/64','invalid']:
            with self.assertRaises(ValueError): scan_network(cidr,'192.168.4.40',24)
        with self.assertRaises(ValueError): scan_network('10.0.0.0/16','10.0.0.1',8)
        self.assertEqual(scan_network('10.0.0.0/31','10.0.0.1',24).num_addresses,2)

    def test_wireless_fields_and_multiple_bssids(self):
        raw='Name : Wi-Fi\nState : connected\nSSID : Test:Lab\nAP BSSID : 00:11:22:33:44:55\nSignal : 72%\nChannel : 44'
        self.assertEqual(parse_wifi(raw)[0]['SSID'],'Test:Lab')
        nearby='SSID 1 : Lab\nAuthentication : WPA3-Personal\nBSSID 1 : 00:11:22:33:44:55\nSignal : 80%\nChannel : 44\nBSSID 2 : 00:11:22:33:44:66\nSignal : 40%\nChannel : 6\nSSID 2 :\nAuthentication : WPA2-Personal'
        rows=parse_access_points(nearby)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1]['security'],'WPA3-Personal')
        self.assertEqual(rows[1]['channel'],'6')
        self.assertEqual(rows[2]['ssid'],'(hidden)')
        self.assertEqual(rows[2]['bssid'],'Not reported')

    @patch('diagnostics.ping',return_value={'ok':False,'ms':None})
    @patch('diagnostics.arp',return_value='00:11:22:33:44:55')
    @patch('diagnostics.resolve_hostname',return_value='printer.lab')
    def test_arp_discovery_without_icmp(self,resolve,arp,ping):
        events=[]
        discover(ipaddress.ip_network('192.168.4.0/30'),'192.168.4.1','local-mac',threading.Event(),lambda k,v:events.append((k,v)))
        hosts=[value for kind,value in events if kind=='scan_host']
        self.assertEqual(len(hosts),2)
        self.assertEqual(next(h for h in hosts if h['ip'].endswith('.2'))['hostname'],'printer.lab')
        self.assertEqual(next(h for h in hosts if h['ip'].endswith('.2'))['method'],'ARP')
        self.assertEqual(next(h for h in hosts if h['ip'].endswith('.1'))['method'],'Local adapter')

    @patch('diagnostics.ping',return_value={'ok':False,'ms':None})
    @patch('diagnostics.arp',return_value='')
    def test_no_false_positive_and_stop(self,arp,ping):
        stop=threading.Event(); events=[]
        def emit(kind,value):
            events.append((kind,value)); stop.set()
        discover(ipaddress.ip_network('192.168.4.0/24'),'192.168.5.1','',stop,emit)
        self.assertFalse(any(k=='scan_host' for k,v in events))
        self.assertLessEqual(arp.call_count,24)

if __name__=='__main__': unittest.main()
