import datetime
import ipaddress
import json
import queue
import re
import socket
import subprocess
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import ttk, filedialog, messagebox
from network_core import inventory, subnet, decode_lldp, cable_assessment, CREATE_NO_WINDOW
from diagnostics import ping, scan_network, discover, wireless_snapshot
from topology import build_map, svg_map

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('LinkScope Live • Windows Network Tester')
        self.geometry('1240x880')
        self.minsize(1050, 760)
        self.configure(bg='#141714')
        self.events = queue.Queue()
        self.adapters, self.neighbors = [], {}
        self.stop_event = threading.Event()
        self.capturing = False
        self.scanning = False
        self.scan_stop = threading.Event()
        self.scan_results = []
        self.scan_context = {}
        self.wifi = {}
        self.wifi_busy = False
        self.inventory_busy = False
        self.monitoring = False
        self.monitor_busy = False
        self.monitor_generation = 0
        self.samples = deque(maxlen=60)
        self.sent = self.received = 0
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10),background='#141714',foreground='#edf2e9')
        style.configure('TFrame', background='#141714')
        style.configure('TLabel', background='#141714')
        style.configure('TButton', padding=(12, 8),background='#303c29',foreground='#f5f9ef',borderwidth=0)
        style.map('TButton',background=[('active','#46612e')],foreground=[('disabled','#87917e')])
        style.configure('TEntry',fieldbackground='#232b20',foreground='#f0f5e9',insertcolor='white')
        style.configure('TCombobox',fieldbackground='#232b20',background='#303c29',foreground='#f0f5e9',arrowcolor='#a6ce39')
        style.map('TCombobox',fieldbackground=[('readonly','#232b20')],foreground=[('readonly','#f0f5e9')])
        style.configure('TNotebook',background='#141714',borderwidth=0)
        style.configure('TNotebook.Tab',padding=(15,12),background='#242b21',foreground='#acb5a2')
        style.map('TNotebook.Tab',background=[('selected','#a6ce39')],foreground=[('selected','#17210d')])
        style.configure('Treeview',rowheight=31,background='#1d241b',fieldbackground='#1d241b',foreground='#edf2e9',borderwidth=0)
        style.configure('Treeview.Heading',background='#303c29',foreground='#b7c4a7',padding=8)
        style.map('Treeview',background=[('selected','#4c652d')])
        style.configure('Accent.TButton',background='#a6ce39',foreground='#17210d')
        style.map('Accent.TButton',background=[('disabled','#303c29'),('active','#b9e04c')],foreground=[('disabled','#87917e')])
        style.configure('Horizontal.TProgressbar',background='#a6ce39',troughcolor='#232b20')
        outer = ttk.Frame(self, padding=22)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='LinkScope  /  LIVE', font=('Segoe UI', 26, 'bold'),foreground='#a6ce39').pack(anchor='w')
        ttk.Label(outer, text='NETWORK OPERATIONS   •   WIRED + WIRELESS   •   DEVICE DISCOVERY', foreground='#a6b39a').pack(anchor='w', pady=(0,16))
        bar = ttk.Frame(outer)
        bar.pack(fill='x')
        self.choice = ttk.Combobox(bar, state='readonly', width=68)
        self.choice.pack(side='left', fill='x', expand=True)
        self.choice.bind('<<ComboboxSelected>>', self.show_adapter)
        self.refresh_button = ttk.Button(bar, text='Refresh adapters', command=self.refresh)
        self.refresh_button.pack(side='left', padx=8)
        ttk.Button(bar, text='Export report', command=self.export).pack(side='left')
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both', expand=True, pady=16)
        local = ttk.Frame(self.tabs, padding=14)
        lldp = ttk.Frame(self.tabs, padding=14)
        tests = ttk.Frame(self.tabs, padding=14)
        self.dashboard = ttk.Frame(self.tabs,padding=16)
        self.tabs.add(self.dashboard,text='  Overview  ')
        self.tabs.add(local, text='  Adapter & subnet  ')
        self.tabs.add(lldp, text='  LLDP neighbors  ')
        self.tabs.add(tests, text='  Connectivity tests  ')
        self.build_dashboard()
        self.build_wireless()
        self.build_scanner()
        self.build_cable()
        self.build_network_map()
        self.details = self.textbox(local)
        controls = ttk.Frame(lldp)
        controls.pack(fill='x')
        self.start_button = ttk.Button(controls, text='Start listening', command=self.start_capture)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(controls, text='Stop', command=self.stop_capture, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        ttk.Label(lldp, text='Use a wired adapter. Allow 30–120 seconds for switch advertisements.\nLLDP must be enabled on the connected switch; silence does not mean the link is down.', wraplength=950).pack(anchor='w', pady=12)
        self.tree = ttk.Treeview(lldp, columns=('system','port','management','vlan','age'), show='headings', height=7)
        for key, title, width in [('system','Switch / chassis',250),('port','Switch port',180),('management','Management IP',200),('vlan','Advertised PVID',120),('age','Age / TTL',120)]:
            self.tree.heading(key,text=title)
            self.tree.column(key,width=width)
        self.tree.pack(fill='x')
        self.tree.bind('<<TreeviewSelect>>', self.show_neighbor)
        self.neighbor_detail = self.textbox(lldp)
        row = ttk.Frame(tests)
        row.pack(fill='x', pady=(0,12))
        ttk.Label(row,text='Host or IP:').pack(side='left')
        self.target = ttk.Entry(row, width=45)
        self.target.pack(side='left', padx=10)
        self.test_button = ttk.Button(row,text='Ping + DNS',command=self.run_test)
        self.test_button.pack(side='left')
        ttk.Label(tests,text='Tests use the Windows routing table. Ping includes the selected adapter’s IPv4 source when available.').pack(anchor='w',pady=(0,10))
        self.test_output = self.textbox(tests)
        self.status = tk.StringVar(value='Loading adapters…')
        ttk.Label(outer,textvariable=self.status,foreground='#a6b39a',wraplength=1150).pack(anchor='w')
        self.tabs.bind('<<NotebookTabChanged>>',self.tab_changed)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(150,self.poll)
        self.refresh()
        self.after(15000,self.auto_refresh)
        self.after(1000,self.monitor_tick)

    def build_network_map(self):
        page=ttk.Frame(self.tabs,padding=14); self.tabs.add(page,text='  Topology  ')
        row=ttk.Frame(page); row.pack(fill='x')
        ttk.Label(row,text='Scan range:').pack(side='left')
        self.map_range=ttk.Entry(row,textvariable=self.scan_range_value,width=24); self.map_range.pack(side='left',padx=8)
        self.map_scan=ttk.Button(row,text='Scan & build map',style='Accent.TButton',command=self.start_scan); self.map_scan.pack(side='left')
        ttk.Button(row,text='Stop scan',command=self.cancel_scan).pack(side='left',padx=8)
        ttk.Button(row,text='Save map (SVG)',command=self.save_map).pack(side='right')
        ttk.Label(page,textvariable=self.scan_summary,foreground='#a6ce39').pack(anchor='w',pady=12)
        ttk.Label(page,text='LOGICAL TOPOLOGY • Dashed lines = IP membership / configured gateway; physical paths unknown.\nSolid lines = LLDP neighbor advertisements. Double-click a device for connectivity tests.',wraplength=1080).pack(anchor='w',pady=(0,12))
        frame=ttk.Frame(page); frame.pack(fill='both',expand=True)
        self.network_map=tk.Canvas(frame,bg='#141714',highlightthickness=0)
        vs=ttk.Scrollbar(frame,orient='vertical',command=self.network_map.yview); vs.pack(side='right',fill='y')
        hs=ttk.Scrollbar(frame,orient='horizontal',command=self.network_map.xview); hs.pack(side='bottom',fill='x')
        self.network_map.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
        self.network_map.pack(fill='both',expand=True)
        self.network_map.bind('<MouseWheel>',lambda e:self.network_map.yview_scroll(-int(e.delta/120),'units'))

    def map_data(self):
        a=self.selected()
        peers=list(self.neighbors.values()) if a and a['guid']==self.scan_context.get('guid') else []
        return build_map(self.scan_context,self.scan_results,peers)

    def update_network_map(self):
        graph=self.map_data()
        signature=json.dumps(graph,sort_keys=True)
        if signature==getattr(self,'map_signature',None): return
        self.map_signature=signature
        c=self.network_map; c.delete('all'); c.configure(scrollregion=(0,0,graph['width'],graph['height']))
        if not graph['nodes']:
            c.create_text(550,180,text='Select a wired or wireless adapter, then Scan & build map.',fill='#a6ce39',font=('Segoe UI',16)); return
        nodes={n['id']:n for n in graph['nodes']}
        for edge in graph['edges']:
            a,b=nodes[edge['from']],nodes[edge['to']]
            c.create_line(a['x'],a['y'],b['x'],b['y'],fill='#71894c',width=2,dash=() if edge['kind']=='lldp_advertisement' else (5,5))
        for i,n in enumerate(graph['nodes']):
            x,y=n['x'],n['y']; tag='mapnode'+str(i)
            c.create_rectangle(x-123,y-48,x+123,y+58,fill='#293322',outline='#a6ce39',tags=tag)
            c.create_text(x,y-26,text=n['title'],fill='#a6ce39',font=('Segoe UI',11,'bold'),tags=tag)
            c.create_text(x,y+13,text=n['detail'],fill='#edf2e9',font=('Segoe UI',9),width=230,tags=tag)
            if n.get('ip'): c.tag_bind(tag,'<Double-1>',lambda event,ip=n['ip']:self.test_map_device(ip))

    def test_map_device(self,ip):
        self.target.delete(0,'end'); self.target.insert(0,ip); self.tabs.select(3)

    def save_map(self):
        if not self.scan_context:
            messagebox.showinfo('Scan first','Run a subnet scan to build a map.'); return
        path=filedialog.asksaveasfilename(defaultextension='.svg',initialfile='LinkScope-topology.svg',filetypes=[('SVG image','*.svg')])
        if path:
            try:
                with open(path,'w',encoding='utf-8') as f: f.write(svg_map(self.map_data()))
                self.status.set('Topology saved: '+path)
            except OSError as exc: messagebox.showerror('Export failed',str(exc))

    def build_cable(self):
        page=ttk.Frame(self.tabs,padding=16)
        self.tabs.add(page,text='  Cable / link  ')
        ttk.Label(page,text='ETHERNET CABLE & LINK PARTNER',foreground='#a6ce39',font=('Segoe UI',18,'bold')).pack(anchor='w',pady=(0,12))
        ttk.Button(page,text='Check link now',style='Accent.TButton',command=self.refresh).pack(anchor='w')
        self.cable_summary=tk.StringVar(value='Select a physical Ethernet adapter')
        ttk.Label(page,textvariable=self.cable_summary,font=('Segoe UI',19,'bold'),foreground='#a6ce39',wraplength=950).pack(anchor='w',pady=18)
        self.cable_details=self.textbox(page)
        ttk.Label(page,text='Continuity / wiremap: NOT MEASURED  •  PoE voltage: NOT MEASURED\nA standard network adapter cannot certify opens, shorts, crossed pairs, cable length, or PoE power.',wraplength=950,foreground='#b0bea0').pack(anchor='w',pady=15)

    def update_cable(self):
        a=self.selected(); result=cable_assessment(a)
        self.cable_summary.set(result['state'])
        lines=[f"Adapter: {a['name'] if a else 'None'}",f"Last configuration sample: {getattr(self,'inventory_time','Not sampled')}",'',f"Link partner: {result['powered_peer']}",f"Negotiated speed: {result['speed']}",'',result['detail'],'','Switch identification:']
        if a and a.get('hardware') and a.get('interface_type')==6 and a['status']=='Up':
            live=[n for n in self.neighbors.values() if time.monotonic()-n['_seen']<n['ttl']]
            if live:
                for n in live: lines.append(f"LLDP: {n['system_name'] or n['chassis']} | Port: {n['port']} | Capabilities: {n['capabilities'] or 'Not advertised'}")
            else: lines.append('No current LLDP neighbor. Use LLDP neighbors > Start listening to identify the remote device (Npcap required).')
        else: lines.append('Requires an active physical Ethernet link; a switch cannot be identified from cable presence alone.')
        lines += ['', 'Continuity: '+result['continuity'],'','Link up is evidence of a working negotiated link, not a pass for every conductor. No IP address is required to detect the Ethernet link.','', 'Configuration refreshes every 15 seconds while capture and discovery are idle. Use Check link now for a fresh sample.']
        text='\n'.join(lines)
        if text!=getattr(self,'last_cable_text',None):
            self.put(self.cable_details,text); self.last_cable_text=text

    def build_dashboard(self):
        row = ttk.Frame(self.dashboard); row.pack(fill='x')
        self.card_vars = []
        for title in ('LINK STATE','LINK SPEED','LOCAL IPv4','DEFAULT GATEWAY'):
            card = tk.Frame(row,bg='#293322',padx=18,pady=15)
            card.pack(side='left',fill='both',expand=True,padx=4)
            tk.Label(card,text=title,bg='#293322',fg='#b0bea0',font=('Segoe UI',9,'bold')).pack(anchor='w')
            value = tk.StringVar(value='—'); self.card_vars.append(value)
            tk.Label(card,textvariable=value,bg='#293322',fg='#a6ce39',font=('Segoe UI',19,'bold')).pack(anchor='w',pady=(7,0))
        self.topology = tk.Canvas(self.dashboard,height=140,bg='#141714',highlightthickness=0)
        self.topology.pack(fill='x',pady=12)
        self.topology.bind('<Configure>',lambda e:self.draw_topology())
        controls = ttk.Frame(self.dashboard); controls.pack(fill='x')
        self.monitor_button = ttk.Button(controls,style='Accent.TButton',text='Start live gateway test',command=self.toggle_monitor)
        self.monitor_button.pack(side='left')
        self.monitor_summary = tk.StringVar(value='Ready • Source-bound IPv4 gateway test, every 2 seconds')
        ttk.Label(controls,textvariable=self.monitor_summary,foreground='#c2ceb5').pack(side='left',padx=15)
        self.graph = tk.Canvas(self.dashboard,height=165,bg='#1d241b',highlightthickness=0)
        self.graph.pack(fill='both',expand=True,pady=14)
        self.graph.bind('<Configure>',lambda e:self.draw_graph())
        ttk.Label(self.dashboard,text='LIVE LATENCY  /  LAST 60 SAMPLES     •     RED MARKS = NO ECHO REPLY',foreground='#a6b39a').pack(anchor='w')
        ttk.Label(self.dashboard,text='Adapter configuration refreshes every 15 seconds. Gateway tests follow Windows routing with the selected IPv4 source.').pack(anchor='w',pady=10)

    def draw_topology(self):
        c = self.topology; c.delete('all')
        a = self.selected(); width = max(c.winfo_width(),900)
        xs = [width*.17,width*.50,width*.83]
        color = '#a6ce39' if a and a['status']=='Up' else '#ff897b'
        for x,y in zip(xs,xs[1:]): c.create_line(x+85,60,y-85,60,fill=color,width=2,dash=(5,5))
        switch = next(iter(self.neighbors.values()),{})
        labels = [('THIS COMPUTER',a['name'] if a else 'No adapter'),('ACCESS LINK',switch.get('system_name') or ('Link up' if a and a['status']=='Up' else 'Link down')),('GATEWAY',next((x for x in a['gateway'] if x),'Not configured') if a else 'Unknown')]
        for x,(label,value) in zip(xs,labels):
            c.create_rectangle(x-88,25,x+88,98,fill='#293322',outline='#546844')
            c.create_text(x,43,text=label,fill='#b0bea0',font=('Segoe UI',9,'bold'))
            c.create_text(x,71,text=value,fill=color,font=('Segoe UI',11,'bold'),width=165)
        c.create_text(width/2,122,text='Local link view • gateway configuration does not prove reachability',fill='#a6b39a',font=('Segoe UI',9))

    def draw_graph(self):
        c = self.graph; c.delete('all'); w,h = max(c.winfo_width(),800),max(c.winfo_height(),150)
        maximum = max([10]+[x for x in self.samples if x is not None])*1.25
        for fraction in (0,.5,1):
            y = 25+(h-50)*fraction
            c.create_line(60,y,w-20,y,fill='#36432e')
            c.create_text(8,y,text=f'{maximum*(1-fraction):.0f} ms',anchor='w',fill='#a6b39a',font=('Segoe UI',9))
        previous = None
        for i,sample in enumerate(self.samples):
            x = 65+i*(w-90)/59
            if sample is None:
                c.create_line(x,h-30,x,h-20,fill='#ff897b',width=3); previous=None
            else:
                y = h-25-(sample/maximum)*(h-50)
                if previous: c.create_line(*previous,x,y,fill='#a6ce39',width=2)
                c.create_oval(x-2,y-2,x+2,y+2,fill='#a6ce39',outline=''); previous=(x,y)
        if not self.samples: c.create_text(w/2,h/2,text='Start a live test to measure gateway response',fill='#a6b39a',font=('Segoe UI',12))

    def toggle_monitor(self):
        if self.monitoring:
            self.monitoring = False; self.monitor_generation += 1
            self.monitor_button.configure(text='Start live gateway test'); return
        a = self.selected()
        if not a or not a['ipv4'] or not any(a['gateway']):
            messagebox.showinfo('Gateway needed','Select a live IPv4 adapter with a gateway.'); return
        self.samples.clear(); self.sent = self.received = 0
        self.monitoring = True; self.monitor_generation += 1
        self.monitor_button.configure(text='Stop live test')

    def monitor_tick(self):
        a = self.selected()
        if self.monitoring and not self.monitor_busy and a and a['ipv4'] and any(a['gateway']):
            generation = self.monitor_generation
            source = a['ipv4'][0]['address']; gateway = next(x for x in a['gateway'] if x)
            self.monitor_busy = True
            def worker():
                try: result = ping(gateway,source)
                except Exception as exc: result = {'ok':False,'ms':None,'error':str(exc)}
                self.events.put(('monitor',(generation,gateway,result)))
            threading.Thread(target=worker,daemon=True).start()
        elif self.monitoring and (not a or not a['ipv4'] or not any(a['gateway'])):
            self.monitor_summary.set('Waiting for an IPv4 adapter with a gateway…')
        self.after(2000,self.monitor_tick)

    def tab_changed(self,event=None):
        if self.tabs.select()==str(self.wireless_tab) and not self.wifi: self.refresh_wifi()

    def build_wireless(self):
        self.wireless_tab = ttk.Frame(self.tabs,padding=14)
        self.tabs.add(self.wireless_tab,text='  Wireless  ')
        row = ttk.Frame(self.wireless_tab); row.pack(fill='x')
        self.wifi_button = ttk.Button(row,text='Refresh wireless',command=self.refresh_wifi)
        self.wifi_button.pack(side='left')
        self.wifi_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(row,text='Refresh every 15 seconds while open',variable=self.wifi_auto).pack(side='left',padx=14)
        self.wifi_summary = tk.StringVar(value='Read Wi-Fi connection and nearby access points')
        ttk.Label(self.wireless_tab,textvariable=self.wifi_summary,foreground='#a6ce39',wraplength=1100,font=('Segoe UI',12,'bold')).pack(anchor='w',pady=12)
        self.signal_history = deque(maxlen=60)
        self.signal_graph = tk.Canvas(self.wireless_tab,height=70,bg='#1d241b',highlightthickness=0)
        self.signal_graph.pack(fill='x',pady=(0,10))
        self.signal_graph.bind('<Configure>',lambda e:self.draw_signal())
        self.ap_tree = self.table(self.wireless_tab,[('ssid','SSID',200),('bssid','BSSID',170),('signal','Signal',90),('channel','Channel',80),('band','Band',80),('radio','Radio',100),('security','Security',170)],height=6)
        ttk.Label(self.wireless_tab,text='Select the Wi-Fi adapter above, then use Overview for live gateway loss/latency or Connectivity tests for ping + DNS.\nSignal is reported by the adapter; nearby results are Windows scan/cache data, not a spectrum analysis.',wraplength=1100).pack(anchor='w',pady=10)
        self.wifi_raw = self.textbox(self.wireless_tab)

    def table(self,parent,columns,height=10):
        frame = ttk.Frame(parent); frame.pack(fill='both',expand=True)
        tree = ttk.Treeview(frame,columns=[x[0] for x in columns],show='headings',height=height)
        for key,title,width in columns: tree.heading(key,text=title); tree.column(key,width=width,minwidth=70)
        scroll = ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        tree.configure(yscrollcommand=scroll.set); scroll.pack(side='right',fill='y'); tree.pack(fill='both',expand=True)
        return tree

    def draw_signal(self):
        c = self.signal_graph; c.delete('all'); w=max(800,c.winfo_width())
        c.create_text(12,13,text='SIGNAL HISTORY  /  %',anchor='w',fill='#a6b39a',font=('Segoe UI',9))
        last=None
        for i,value in enumerate(self.signal_history):
            if value is None: last=None; continue
            x,y=12+i*(w-24)/59,64-value*.4
            if last: c.create_line(*last,x,y,fill='#a6ce39',width=2)
            c.create_oval(x-2,y-2,x+2,y+2,fill='#a6ce39',outline=''); last=(x,y)

    def refresh_wifi(self):
        if self.wifi_busy: return
        self.wifi_busy=True; self.wifi_button.configure(state='disabled')
        self.wifi_summary.set('Reading Windows wireless information…')
        def worker():
            try: self.events.put(('wifi',wireless_snapshot()))
            except Exception as exc: self.events.put(('wifi_error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def build_scanner(self):
        page = ttk.Frame(self.tabs,padding=14); self.tabs.add(page,text='  Subnet discovery  ')
        row = ttk.Frame(page); row.pack(fill='x')
        ttk.Label(row,text='IPv4 range:').pack(side='left')
        self.scan_range_value=tk.StringVar()
        self.scan_range = ttk.Entry(row,width=25,textvariable=self.scan_range_value); self.scan_range.pack(side='left',padx=10)
        self.scan_button = ttk.Button(row,style='Accent.TButton',text='Scan subnet',command=self.start_scan); self.scan_button.pack(side='left')
        self.scan_stop_button = ttk.Button(row,text='Stop',command=self.cancel_scan,state='disabled'); self.scan_stop_button.pack(side='left',padx=8)
        self.scan_summary = tk.StringVar(value='Ready • Select a connected adapter and scan its local subnet')
        ttk.Label(page,textvariable=self.scan_summary,foreground='#a6ce39').pack(anchor='w',pady=12)
        self.scan_progress = ttk.Progressbar(page,mode='determinate'); self.scan_progress.pack(fill='x',pady=(0,12))
        self.scan_tree = self.table(page,[('ip','IPv4 address',150),('hostname','Hostname',240),('mac','MAC address',210),('ms','Ping RTT',130),('method','Discovered by',200)],height=13)
        self.scan_tree.bind('<Double-1>',self.test_discovered)
        ttk.Label(page,text='ARP + ICMP discovery • 24 concurrent probes • Up to 4,096 addresses per scan\nDouble-click a device to open connectivity tests. Devices may block ping or be hidden by Wi-Fi client isolation.\nA MAC response can come from the Windows ARP cache or proxy ARP; discovery is not an exhaustive inventory.',wraplength=1100).pack(anchor='w',pady=14)

    def start_scan(self):
        if self.scanning: return
        a = self.selected()
        if not a or a['status']!='Up' or not a['ipv4']:
            messagebox.showinfo('Live IPv4 adapter needed','Choose a connected adapter with an IPv4 address.'); return
        try:
            network=None
            for address in a['ipv4']:
                try: network=scan_network(self.scan_range.get(),address['address'],address['prefix']); source=address['address']; break
                except ValueError: pass
            if network is None: raise ValueError('Enter an IPv4 CIDR range within this adapter’s subnet, no larger than /20.')
        except ValueError as exc: messagebox.showerror('Scan range',str(exc)); return
        self.scanning=True; self.scan_stop=threading.Event(); self.scan_results=[]
        stop=self.scan_stop
        self.scan_context={'adapter':a['name'],'source':source,'network':str(network),'started':datetime.datetime.now().astimezone().isoformat(),'state':'running'}
        self.scan_context.update(guid=a['guid'],hostname=socket.gethostname(),gateway=next((x for x in a['gateway'] if x),None),local_network=str(ipaddress.ip_network(f"{source}/{address['prefix']}",strict=False)))
        self.scan_tree.delete(*self.scan_tree.get_children()); self.scan_progress['value']=0
        self.scan_summary.set(f'Scanning {network} from {source}…')
        self.scan_button.configure(state='disabled'); self.scan_stop_button.configure(state='normal'); self.scan_range.configure(state='disabled'); self.lock_adapter()
        def worker():
            error=None
            try: discover(network,source,a['mac'],stop,lambda kind,data:self.events.put((kind,data)))
            except Exception as exc: error=str(exc)
            self.events.put(('scan_done',(stop.is_set(),error)))
        threading.Thread(target=worker,daemon=True).start()

    def cancel_scan(self):
        self.scan_stop.set(); self.scan_stop_button.configure(state='disabled'); self.scan_summary.set('Stopping after in-flight probes finish…')

    def test_discovered(self,event=None):
        selected=self.scan_tree.selection()
        if selected:
            self.target.delete(0,'end'); self.target.insert(0,self.scan_tree.item(selected[0],'values')[0]); self.tabs.select(3)

    def lock_adapter(self):
        locked=self.scanning or self.capturing
        self.choice.configure(state='disabled' if locked else 'readonly')
        self.refresh_button.configure(state='disabled' if locked or self.inventory_busy else 'normal')
        self.map_scan.configure(state='disabled' if self.scanning else 'normal')
        self.map_range.configure(state='disabled' if self.scanning else 'normal')

    def auto_refresh(self):
        if not self.scanning and not self.capturing: self.refresh()
        if self.tabs.select()==str(self.wireless_tab) and self.wifi_auto.get(): self.refresh_wifi()
        self.after(15000,self.auto_refresh)

    def textbox(self,parent):
        frame=ttk.Frame(parent); frame.pack(fill='both',expand=True,pady=(10,0))
        box = tk.Text(frame, wrap='word', font=('Consolas',10), bg='#1d241b', fg='#dde7d3', relief='flat', padx=16,pady=14,state='disabled',height=8)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=box.yview)
        box.configure(yscrollcommand=scroll.set); scroll.pack(side='right',fill='y'); box.pack(fill='both',expand=True)
        return box

    def put(self,box,text):
        box.configure(state='normal'); box.delete('1.0','end'); box.insert('1.0',text); box.configure(state='disabled')

    def selected(self):
        i = self.choice.current()
        return self.adapters[i] if 0 <= i < len(self.adapters) else None

    def refresh(self):
        if self.inventory_busy: return
        self.inventory_busy = True
        self.refresh_button.configure(state='disabled')
        self.status.set('Reading Windows adapter configuration…')
        def worker():
            try: self.events.put(('inventory',inventory()))
            except Exception as exc: self.events.put(('inventory_error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def show_adapter(self,event=None):
        a = self.selected()
        if not a: return
        if event:
            self.monitor_generation += 1
            self.samples.clear(); self.sent = self.received = 0
            self.monitor_summary.set('Adapter changed • Waiting for next gateway sample' if self.monitoring else 'Ready • Source-bound IPv4 gateway test, every 2 seconds')
            self.neighbors.clear(); self.tree.delete(*self.tree.get_children()); self.put(self.neighbor_detail,'')
            self.draw_graph()
        lines = [a['name'],a['description'],'',f"Link: {a['status']}    Speed: {a['speed']}",f"MAC: {a['mac']}    Interface index: {a['index']}",f"Gateway: {', '.join(x for x in a['gateway'] if x) or 'None'}",f"DNS: {', '.join(x for x in a['dns'] if x) or 'None'}"]
        for addr in a['ipv4']:
            s = subnet(addr['address'],addr['prefix'])
            lines += ['',f"IPv4:       {addr['address']}/{addr['prefix']}",f"Subnet:     {s['network']}",f"Mask:       {s['mask']}",f"Broadcast:  {s['broadcast']}",f"Host range: {s['first']} – {s['last']} ({s['hosts']:,} addresses)"]
        lines += ['', 'IPv6: ' + (', '.join(a['ipv6']) or 'None')]
        self.put(self.details,'\n'.join(lines))
        if event or not self.target.get():
            self.target.delete(0,'end'); self.target.insert(0,next((x for x in a['gateway'] if x),'1.1.1.1'))
        if event or not self.scan_range.get():
            self.scan_range.delete(0,'end')
            if a['ipv4']:
                addr = a['ipv4'][0]
                self.scan_range.insert(0,subnet(addr['address'],addr['prefix'])['network'])
        values = [a['status'].upper(),a['speed'],a['ipv4'][0]['address'] if a['ipv4'] else 'No IPv4',next((x for x in a['gateway'] if x),'No gateway')]
        for variable,value in zip(self.card_vars,values): variable.set(value)
        self.draw_topology()
        self.update_cable()

    def start_capture(self):
        a = self.selected()
        if not a or a['status'] != 'Up':
            messagebox.showinfo('Select a live adapter','Choose an adapter with link status Up.'); return
        self.stop_event = threading.Event()
        stop = self.stop_event
        self.capturing = True
        self.start_button.configure(state='disabled'); self.stop_button.configure(state='normal')
        self.lock_adapter()
        self.neighbors.clear(); self.tree.delete(*self.tree.get_children()); self.put(self.neighbor_detail,'')
        self.status.set(f"Preparing capture on {a['name']}…")
        def worker():
            try:
                from scapy.all import conf, sniff
                conf.ifaces.reload()
                guid = a['guid'].strip('{}').lower()
                iface = next((i for i in conf.ifaces.values() if guid in str(getattr(i,'guid','')).lower() or guid in str(getattr(i,'network_name','')).lower()),None)
                if iface is None: raise RuntimeError('Npcap interface not found. Install Npcap, then restart LinkScope.')
                def receive(packet):
                    try:
                        item = decode_lldp(bytes(packet))
                        if item: self.events.put(('neighbor',item))
                    except ValueError: pass
                with conf.L2listen(iface=iface,filter='ether proto 0x88cc or (vlan and ether proto 0x88cc)') as capture:
                    self.events.put(('status',f"Listening on {a['name']}. Waiting for LLDP advertisements…"))
                    while not stop.is_set():
                        sniff(opened_socket=capture,prn=receive,store=False,timeout=1)
            except Exception as exc:
                self.events.put(('status',f'Capture unavailable: {exc}. Npcap is required; administrator access may be required by its installation settings.'))
            finally: self.events.put(('capture_done',None))
        threading.Thread(target=worker,daemon=True).start()

    def stop_capture(self):
        self.stop_event.set(); self.stop_button.configure(state='disabled')
        self.status.set('Stopping LLDP listener…')

    def show_neighbor(self,event=None):
        selected = self.tree.selection()
        if selected and selected[0] in self.neighbors:
            item = {k:v for k,v in self.neighbors[selected[0]].items() if k != '_seen'}
            self.put(self.neighbor_detail,json.dumps(item,indent=2))

    def run_test(self):
        target = self.target.get().strip()
        try: ipaddress.ip_address(target); valid = True
        except ValueError: valid = bool(re.fullmatch(r'(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?',target))
        if not valid:
            messagebox.showerror('Invalid target','Enter a hostname or IP address.'); return
        a = self.selected()
        source = a['ipv4'][0]['address'] if a and a['ipv4'] else None
        self.test_button.configure(state='disabled'); self.put(self.test_output,f'Testing {target}…')
        def worker():
            lines = []
            try:
                result = subprocess.run(['ping.exe','-4','-n','4','-w','1500'] + (['-S',source] if source else []) + [target],capture_output=True,text=True,errors='replace',timeout=15,creationflags=CREATE_NO_WINDOW)
                lines.append(result.stdout or result.stderr)
                # nslookup has a bounded subprocess lifetime even when the DNS server is unavailable.
                dns = subprocess.run(['nslookup.exe',target],capture_output=True,text=True,errors='replace',timeout=12,creationflags=CREATE_NO_WINDOW)
                lines += ['DNS lookup (system DNS):',dns.stdout,dns.stderr]
            except Exception as exc: lines.append(str(exc))
            self.events.put(('test','\n'.join(lines)))
        threading.Thread(target=worker,daemon=True).start()

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension='.json',initialfile='LinkScope-report.json',filetypes=[('JSON report','*.json')])
        if not path: return
        report = {'created':datetime.datetime.now().astimezone().isoformat(),'adapters':self.adapters,'neighbors':[{k:v for k,v in n.items() if k != '_seen'} for n in self.neighbors.values()],'connectivity_test':self.test_output.get('1.0','end').strip(),'wireless':self.wifi,'subnet_scan':{'context':self.scan_context,'devices':self.scan_results},'live_gateway_test':{'adapter':self.selected()['name'] if self.selected() else None,'sent':self.sent,'received':self.received,'last_60_rtt_ms':list(self.samples)}}
        try:
            report['cable_link']={'adapter':self.selected()['name'] if self.selected() else None,'sampled_at':getattr(self,'inventory_time',None),**cable_assessment(self.selected())}
            report['topology']=self.map_data()
            with open(path,'w',encoding='utf-8') as f: json.dump(report,f,indent=2)
            self.status.set(f'Report saved: {path}')
        except OSError as exc: messagebox.showerror('Export failed',str(exc))

    def poll(self):
        try:
            while True:
                kind,data = self.events.get_nowait()
                if kind == 'inventory':
                    self.inventory_time=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
                    previous=self.selected()
                    guid=previous['guid'] if previous else None
                    self.adapters = sorted(data,key=lambda a:(a['status'] != 'Up',not bool(a['gateway'] and any(a['gateway'])),a['name']))
                    self.choice['values'] = [f"{a['name']}  •  {a['status']}  •  {a['speed']}" for a in self.adapters]
                    index=next((i for i,a in enumerate(self.adapters) if a['guid']==guid),0)
                    if self.adapters:
                        self.choice.current(index)
                        current=self.selected()
                        changed=previous and (previous['guid']!=current['guid'] or previous['ipv4']!=current['ipv4'] or previous['gateway']!=current['gateway'] or previous['status']!=current['status'])
                        self.show_adapter(event=True if changed else None)
                    else:
                        self.choice.set('No adapters found'); self.put(self.details,'No Windows network adapters found.')
                        for v in self.card_vars: v.set('Unavailable')
                    self.inventory_busy=False; self.lock_adapter()
                    self.status.set('Adapter configuration updated at '+datetime.datetime.now().strftime('%H:%M:%S'))
                elif kind == 'inventory_error': self.inventory_busy=False; self.lock_adapter(); self.status.set(data)
                elif kind == 'status': self.status.set(data)
                elif kind == 'capture_done':
                    self.capturing = False
                    self.start_button.configure(state='normal'); self.stop_button.configure(state='disabled'); self.lock_adapter()
                    if self.stop_event.is_set(): self.status.set('LLDP listener stopped.')
                elif kind == 'test': self.put(self.test_output,data); self.test_button.configure(state='normal')
                elif kind == 'monitor':
                    self.monitor_busy=False
                    generation,gateway,result=data
                    if generation==self.monitor_generation and self.monitoring:
                        self.sent+=1; self.received+=int(result['ok']); self.samples.append(result['ms'])
                        loss=100*(self.sent-self.received)/self.sent
                        rtt=f"{result['ms']} ms" if result['ok'] else 'No echo reply'
                        self.monitor_summary.set(f"{gateway} • {rtt} • Loss {loss:.1f}% • {self.received}/{self.sent} replies")
                        if result.get('error'): self.status.set(result['error'])
                        self.draw_graph()
                elif kind == 'wifi':
                    self.wifi=data; self.wifi_busy=False; self.wifi_button.configure(state='normal')
                    a=self.selected()
                    interface=next((x for x in data['interfaces'] if a and x.get('Name')==a['name']),next(iter(data['interfaces']),{}))
                    summary='   •   '.join(f"{key}: {interface[key]}" for key in ('Name','State','SSID','Signal','Rssi','Channel','Band','Authentication','Receive rate (Mbps)','Transmit rate (Mbps)') if key in interface)
                    self.wifi_summary.set(summary or 'Wireless details unavailable. See Windows output below; location permission or a Wi-Fi adapter may be needed.')
                    signal=interface.get('Signal','').rstrip('%').strip()
                    identity=(interface.get('Name'),interface.get('SSID'),interface.get('AP BSSID',interface.get('BSSID')))
                    if identity!=getattr(self,'signal_identity',None): self.signal_history.clear()
                    self.signal_identity=identity
                    self.signal_history.append(int(signal) if signal.isdigit() and 0<=int(signal)<=100 else None); self.draw_signal()
                    self.ap_tree.delete(*self.ap_tree.get_children())
                    for ap in data['access_points']: self.ap_tree.insert('','end',values=tuple(ap[k] for k in ('ssid','bssid','signal','channel','band','radio','security')))
                    self.put(self.wifi_raw,data['raw'])
                elif kind == 'wifi_error':
                    self.wifi_busy=False; self.wifi_button.configure(state='normal'); self.wifi_summary.set('Wireless read failed: '+data)
                elif kind == 'scan_host':
                    self.scan_results.append(data)
                    self.scan_tree.insert('','end',iid=data['ip'],values=(data['ip'],data.get('hostname') or 'Hostname unavailable',data['mac'] or 'Unavailable',f"{data['ms']} ms" if data['ms'] is not None else 'No echo',data['method']))
                elif kind == 'scan_progress':
                    completed,total=data
                    self.scan_progress['maximum']=max(1,total); self.scan_progress['value']=completed
                    self.scan_summary.set(f"{self.scan_context['network']} • {completed:,}/{total:,} probed • {len(self.scan_results)} discovered")
                elif kind == 'scan_done':
                    stopped,error=data; self.scanning=False
                    state='Failed' if error else 'Stopped' if stopped else 'Complete'
                    self.scan_context.update(state=state,finished=datetime.datetime.now().astimezone().isoformat(),error=error)
                    self.scan_summary.set(f"{state} • {len(self.scan_results)} devices discovered on {self.scan_context['network']}"+(f' • {error}' if error else ''))
                    self.scan_button.configure(state='normal'); self.scan_stop_button.configure(state='disabled'); self.scan_range.configure(state='normal'); self.lock_adapter()
                    for i,key in enumerate(sorted(self.scan_tree.get_children(),key=ipaddress.ip_address)): self.scan_tree.move(key,'',i)
                elif kind == 'neighbor':
                    key = data['source_mac'] + '|' + data['chassis'] + '|' + data['port']
                    if data['ttl'] == 0:
                        self.neighbors.pop(key,None)
                        if self.tree.exists(key): self.tree.delete(key)
                        continue
                    data['_seen'] = time.monotonic(); data['last_seen'] = datetime.datetime.now().astimezone().isoformat()
                    self.neighbors[key] = data
                    if not self.tree.exists(key): self.tree.insert('','end',iid=key)
                    self.status.set(f"Received LLDP from {data['system_name'] or data['chassis']} on port {data['port']}")
                    self.draw_topology()
        except queue.Empty: pass
        now = time.monotonic()
        for key,n in list(self.neighbors.items()):
            age = int(now - n['_seen'])
            if age >= n['ttl']:
                del self.neighbors[key]
                if self.tree.exists(key): self.tree.delete(key)
            else: self.tree.item(key,values=(n['system_name'] or n['chassis'],n['port'],', '.join(n['management']),n['vlan'],f"{age}s / {n['ttl']}s"))
        self.update_cable()
        self.update_network_map()
        self.after(250,self.poll)

    def close(self):
        self.stop_event.set(); self.scan_stop.set(); self.destroy()

if __name__ == '__main__':
    App().mainloop()
