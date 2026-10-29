"""Evidence-based logical topology and portable SVG export."""
import html
import ipaddress

def build_map(context, devices, neighbors=()):
    if not context: return {'nodes':[], 'edges':[], 'width':1100, 'height':450}
    source=context['source']; gateway=context.get('gateway')
    found={d['ip']:d for d in devices}
    nodes=[{'id':'local','x':180,'y':65,'title':'THIS COMPUTER','detail':source+' • '+context['adapter']+'\n'+context.get('hostname','Hostname unavailable'),'ip':source},
           {'id':'subnet','x':550,'y':210,'title':'LOGICAL IP SUBNET','detail':context.get('local_network',context['network'])}]
    edges=[{'from':'local','to':'subnet','kind':'membership'}]
    if gateway:
        nodes.append({'id':'gateway','x':550,'y':65,'title':'CONFIGURED GATEWAY','detail':(found.get(gateway,{}).get('hostname') or 'Hostname unavailable')[:32]+'\n'+gateway+(' • discovered' if gateway in found else ' • not verified by scan'),'ip':gateway})
        edges.append({'from':'local','to':'gateway','kind':'configured_route'})
    for i,n in enumerate(neighbors):
        key='lldp'+str(i)
        nodes.append({'id':key,'x':920,'y':65+i*105,'title':'LLDP NEIGHBOR','detail':(n.get('system_name') or n['chassis'])+' • '+n['port']})
        edges.append({'from':'local','to':key,'kind':'lldp_advertisement'})
    start=max(340, len(neighbors)*105+160)
    hosts=[d for ip,d in sorted(found.items(),key=lambda p:ipaddress.ip_address(p[0])) if ip not in (source,gateway)]
    for i,d in enumerate(hosts):
        key='host:'+d['ip']
        nodes.append({'id':key,'x':145+(i%4)*270,'y':start+(i//4)*140,'title':d['ip'],'hostname':d.get('hostname',''),'detail':((d.get('hostname') or 'Hostname unavailable')[:32])+'\n'+(d.get('mac') or 'MAC unavailable')+'\n'+d['method']+(f" • {d['ms']} ms" if d.get('ms') is not None else ''),'ip':d['ip']})
        edges.append({'from':'subnet','to':key,'kind':'membership'})
    return {'nodes':nodes,'edges':edges,'width':1100,'height':max(480,start+((len(hosts)+3)//4)*140),'scan':dict(context),'meaning':'Logical IP membership and configured routing; physical paths are unknown. Solid LLDP edges indicate received neighbor advertisements.'}

def svg_map(graph):
    esc=lambda v:html.escape(str(v),quote=True)
    nodes={n['id']:n for n in graph['nodes']}
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{graph["width"]}" height="{graph["height"]+100}" viewBox="0 0 {graph["width"]} {graph["height"]+100}">', '<rect width="100%" height="100%" fill="#141714"/>', '<text x="25" y="25" fill="#a6ce39" font-family="Arial" font-size="18">LinkScope • Logical network topology</text>', '<text x="25" y="49" fill="#b0bea0" font-family="Arial" font-size="12">Dashed: IP membership / configured route. Solid: LLDP advertisement. Physical paths unknown.</text>', '<g transform="translate(0,70)">']
    for e in graph['edges']:
        a,b=nodes[e['from']],nodes[e['to']]
        dash='' if e['kind']=='lldp_advertisement' else ' stroke-dasharray="5 5"'
        parts.append(f'<line x1="{a["x"]}" y1="{a["y"]}" x2="{b["x"]}" y2="{b["y"]}" stroke="#71894c" stroke-width="2"{dash}/>')
    for n in graph['nodes']:
        x,y=n['x'],n['y']
        parts.append(f'<rect x="{x-123}" y="{y-48}" width="246" height="106" rx="7" fill="#293322" stroke="#a6ce39"/>')
        parts.append(f'<text x="{x}" y="{y-26}" text-anchor="middle" font-family="Arial" font-size="13" fill="#a6ce39">{esc(n["title"])}</text>')
        for j,line in enumerate(n['detail'].splitlines()):
            parts.append(f'<text x="{x}" y="{y+7+j*17}" text-anchor="middle" font-family="Arial" font-size="11" fill="#edf2e9">{esc(line)}</text>')
    parts.append('</g></svg>')
    return '\n'.join(parts)
