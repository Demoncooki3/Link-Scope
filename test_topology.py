import unittest
import xml.etree.ElementTree as ET
from topology import build_map, svg_map

class TopologyTests(unittest.TestCase):
    def test_evidence_and_export(self):
        context={'source':'192.168.1.10','adapter':'Ethernet & USB','network':'192.168.1.0/24','gateway':'192.168.1.1'}
        hosts=[{'ip':'192.168.1.20','mac':'00:11:22:33:44:55','method':'ARP','ms':None}]
        graph=build_map(context,hosts)
        self.assertEqual(len(graph['nodes']),4)
        self.assertFalse(any(e['kind']=='lldp_advertisement' for e in graph['edges']))
        self.assertIn('not verified',next(n for n in graph['nodes'] if n['id']=='gateway')['detail'])
        ET.fromstring(svg_map(graph))
        graph=build_map(context,hosts,[{'system_name':'Switch <lab>','chassis':'chassis','port':'Gi1'}])
        self.assertEqual(sum(e['kind']=='lldp_advertisement' for e in graph['edges']),1)
        ET.fromstring(svg_map(graph))

    def test_empty_map(self):
        self.assertFalse(build_map({},[])['nodes'])
