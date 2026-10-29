# LinkScope Live — Windows Network Tester

GitHub repository: [Demoncooki3/Link-Scope](https://github.com/Demoncooki3/Link-Scope).

## Download a Windows build

For the executable, open [Releases](https://github.com/Demoncooki3/Link-Scope/releases/latest) and download **LinkScope.exe** under Assets, or use the portable ZIP. Successful builds on main automatically publish both files to a release.

Open the repository's **Actions** tab, choose a successful **Windows portable build** run, and download the **LinkScope-Windows-x64** artifact. Extract the downloaded artifact and the portable ZIP inside it, then run `LinkScope.exe`. GitHub may require sign-in to download workflow artifacts. Each push runs tests and creates a new build. Older artifacts may expire; build.ps1 can reproduce the application locally.

The current edition uses a lime-green and charcoal theme. The portable package is **dist/LinkScope-Hostnames-Windows-x64.zip**.

Run **dist/hostnames/LinkScope.exe** on Windows 10/11. No Python installation is needed for the executable.

Select an adapter to see its link state, speed, MAC, IPv4 addresses, subnet mask, network, broadcast, host range, IPv6 addresses, gateway, and DNS servers. Active adapters with gateways appear first; use the selector to choose the physical port you are testing. Refresh after moving cables or changing configuration.

## Live dashboard

The Overview tab displays link state, negotiated link speed, IP and gateway cards, a local connection diagram, and an optional continuous gateway test. Click **Start live gateway test** for an IPv4 echo every two seconds, a 60-sample latency graph, and cumulative echo loss. Loss measures missing ICMP replies; it is not a measurement of all application traffic. Link speed is the adapter's negotiated rate, not an Internet speed test. Adapter configuration refreshes every 15 seconds while LLDP capture and discovery are idle. The selected adapter is preserved across refreshes.

## Wireless testing

Open **Wireless** to read the Wi-Fi connection, SSID, signal percentage and history, RSSI where reported, channel, band, security, and receive/transmit link rates. Refresh manually or leave automatic refresh enabled while this tab is open. The nearby network table shows BSSIDs, signal, channel, radio, and security when Windows supplies them; networks without BSSID details remain visible as SSID-only rows.

For Wi-Fi connectivity testing, select the Wi-Fi adapter in the top selector and use Overview's live gateway test or **Connectivity tests**. Signal history resets when the wireless connection identity changes. Nearby network results come from Windows and may be cached. This is not an RF spectrum analyzer or a throughput test.

Windows may require location permission to disclose WLAN details. If unavailable, the original Windows diagnostic output is shown; the app does not change permissions or settings. Structured Wi-Fi fields currently recognize English Windows output; other Windows languages retain the raw output for inspection. No wireless adapter or a stopped WLAN service is reported in that output.

## Subnet discovery

Open **Subnet discovery**. Its CIDR range defaults to the selected adapter's IPv4 subnet. Click **Scan subnet** to discover neighbors using Windows ARP and ICMP APIs, with 24 concurrent probes and no Npcap dependency. Results show IPv4 address, MAC when available, ping latency, and discovery method. Double-click a device to populate Connectivity tests. **Stop** ends scheduling and waits for the in-flight Windows calls to finish.

Ranges must be inside an IPv4 subnet configured on the selected adapter and contain at most 4,096 addresses (/20 or smaller). For larger networks, enter a smaller CIDR range. /31 and /32 ranges are supported. The adapter selector is locked during discovery so results keep their source context. Windows routing still applies, including VPN and overlapping route behavior.

ARP responses can come from cache or proxy ARP. Firewalls, sleeping devices, wireless isolation, and disabled echo replies can hide neighbors; a scan is not proof that every device has been found. Reports include scan range, source adapter, completion state, discovered devices, wireless snapshots, and live test samples.

## LLDP neighbors

Install [Npcap](https://npcap.com/#download) separately, then restart LinkScope. The capture driver is not bundled. Open **LLDP neighbors** and click **Start listening**. If Npcap was installed with administrator-only capture access, run LinkScope as administrator.

Use wired Ethernet with LLDP enabled on the connected switch. Wait 30–120 seconds. The app passively receives advertisements; it does not enable LLDP on your switch or transmit advertisements. Some Windows NICs, drivers, virtual switches, and switch configurations may prevent LLDP packets from reaching capture software. A working Ethernet link can have no visible LLDP neighbors.

Neighbor details include switch name, chassis ID, switch port, port description, management IP, enabled capabilities, advertised port VLAN ID when supplied, and system description. The advertised PVID is switch information, not proof of your computer's assigned VLAN. Entries expire using the switch's TTL; shutdown advertisements remove entries immediately. Starting a new capture clears old neighbors.

## Connectivity and reports

**Ping + DNS** runs four IPv4 pings with the selected adapter's IPv4 source where available, followed by a system DNS lookup. Windows routing still determines the outgoing path; DNS uses the system resolver configuration. A blocked ping alone does not prove a host is unreachable. Export saves adapter details, currently visible neighbors, timestamps, and test output as JSON.

## Run from source / rebuild

Requires Python 3.12 on Windows. Run `python -m pip install -r requirements.txt`, then `python app.py`.

To build the portable executable, run `powershell -ExecutionPolicy Bypass -File build.ps1` from this folder. Output: `dist/hostnames/LinkScope.exe`. Run tests with `python -m unittest -v`.

LLDP decoding handles Ethernet and VLAN-tagged Ethernet frames. Packet capture uses Scapy and Npcap. See [Scapy Windows setup](https://scapy.readthedocs.io/en/stable/installation.html) and [Wireshark LLDP reference](https://wiki.wireshark.org/LinkLayerDiscoveryProtocol).

## Cable / link check

Select a physical Ethernet adapter and open Cable / link. Check link now reads current Windows link state. Active Ethernet link indicates an active remote Ethernet transceiver, even without an IP address. It does not prove that the whole remote device is booted. LLDP can identify the remote device and port when advertised.

No link cannot distinguish a disconnected or faulty cable, an unpowered device, a disabled port, or negotiation failure. Wi-Fi and virtual adapters are excluded. Continuity, wiremap, per-pair faults, cable length, and PoE voltage require diagnostic hardware and are explicitly not measured. This application does not implement a hardware continuity test.

## Network topology

Open Topology, select a wired or wireless adapter, choose its local IPv4 CIDR range, and click Scan & build map. The map fills as ARP/ICMP discovery returns devices. It shows this computer, the configured gateway, and discovered IP/MAC addresses. Dashed edges represent logical IP membership or a configured route, not measured switch connections. Solid edges represent current LLDP neighbor advertisements on the scan adapter. Hidden devices and switches/APs without discovery responses may be absent. Physical downstream switch ports and AP client attachments cannot be inferred from this scan.

Scroll the map for larger scans. Double-click a device for connectivity tests. Save map (SVG) exports a standalone image; Export report includes structured nodes, edges, scan context, and cable/link results. A completed or stopped map retains its original adapter and range even if you select another adapter. The next scan replaces it.

Discovered devices now include hostnames from reverse DNS (PTR records), using the Windows DNS configuration. Lookups have a four-second timeout. Missing names show as Hostname unavailable. The local computer uses its Windows hostname. Names appear in discovery, topology, SVG, and JSON reports. Long names are shortened on map cards; full names remain in the discovery table and device report. Run a new scan to populate names.
