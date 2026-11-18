# Cisco Packet Tracer Automatic IP Planner & VLSM Subnet Generator

A modular Python application and visual web interface that automatically discovers network topologies from Cisco Packet Tracer (`.pkt`) files, partitions them into broadcast domains, plans non-overlapping subnets using Variable Length Subnet Masking (VLSM), configures static IP addresses, default gateways, and router interfaces, and outputs a verified `.pkt` file ready for ping testing.

---

## Key Features

- **Automated Topology Discovery**: Parses `.pkt` files and detects routers, switches, and end devices along with their cable connections.
- **Broadcast Domain & Subnet Detection**: Uses graph traversal across Layer 2 infrastructure to automatically group devices into subnets and identify default gateways.
- **Interactive Boundary Confirmation**: Visualizes the topology in an interactive SVG map and allows users to confirm, rename, or adjust spare IP host padding for each subnet before allocation.
- **VLSM Optimal Address Planning**: Computes non-overlapping subnets from any starting IPv4 block (e.g. `192.168.1.0/24`, `10.0.0.0/16`), sorting by host demand to eliminate address fragmentation.
- **Non-Destructive File Generation**: Generates a new `.pkt` file with configured static IPs, subnet masks, default gateways, and router interfaces while preserving the original file unchanged.
- **Automatic Inter-Subnet Routing**: Computes and injects static routes (`ip route ...`) for multi-router networks to enable end-to-end communication across router hops.
- **Integrated ICMP Ping PDUs**: Embeds Simple PDU ping tests directly into the `.pkt` file for instant one-click verification in Packet Tracer.
- **Comprehensive Validation**: Guards against insufficient address space, duplicate IPs, unsupported GUI-only devices, disconnected devices, and isolated subnets.
- **Practical Fallback Outputs**: Generates ready-to-paste Cisco IOS CLI scripts (`.ios`) and an address table (`.csv`, Markdown) for manual application.
- **Dual Interfaces**: Includes both a beginner-friendly Flask Web UI and a headless CLI.

---

## Investigation of `pktlib` & Packet Tracer Compatibility

As part of the design of this application, we conducted an empirical investigation into `pktlib` and Cisco Packet Tracer file structures:

### 1. Underlying File Structure
Packet Tracer `.pkt` files are not plain text or simple ZIP archives. They use a proprietary multi-layer container format:
1. **Outer Scrambler**: The entire file is byte-reversed and XORed with `(L - i*L) & 0xFF`, where `L` is file length.
2. **Twofish-EAX Cipher**: Encrypted with Twofish in EAX authenticated mode (16-byte fixed key, 16-byte nonce, 16-byte authentication tag).
3. **Inner Scrambler**: Plaintext XORed with `(n - i) & 0xFF`.
4. **Qt qCompress / Zlib**: Qt compressed stream containing the inner XML document (`PACKETTRACER5`).

### 2. Capabilities of `pktlib`
- **Safe In-Memory Mutation**: Modifies the underlying XML element tree directly (`IP`, `SUBNET`, `PORT_GATEWAY`, and router `RUNNINGCONFIG`).
- **Preservation of Network Metadata**: Non-IP properties (device coordinates, custom cables, modules, layout shapes, notes) remain completely intact upon saving.
- **Cisco IOS Running Config Generation**: Setting `router[port].address = "192.168.1.1/24"` automatically generates standard Cisco IOS commands (`interface ...`, `ip address ...`, and `no shutdown`).
- **Ping PDU Injection**: Supports adding Packet Tracer simulation PDUs (`net.ping(src, dst)`).

### 3. Version Compatibility Findings
- `pktlib` contains a built-in edition table with a single stamp: `8.2: 8.2.0.0162`.
- When called with the default `strict=True`, `pktlib.load()` **rejects** files saved by newer Packet Tracer builds (such as 8.2.1, 8.2.2, 8.3) with a `FileFormatError`.
- **Solution & Best Practice**: Our application explicitly uses `strict=False` when calling `pktlib.load()`. In our automated tests against Cisco Packet Tracer 8.2.2 on Windows, files saved with `strict=False` opened seamlessly without errors or corruption.

### 4. Known Device Quirks & Practical Fallbacks
- **GUI-Only Devices**: Devices such as `WirelessRouter` (e.g. WRT300N), `HomeGateway`, and `CentralOfficeServer` cannot be configured via IOS text and will raise a `PktError`. The application flags these devices as unsupported for automatic write-back and provides manual setup guidance.
- **IP Phones**: Cisco Packet Tracer drops IP phone config from offline files.
- **Bluetooth Interfaces**: PCs contain an `eBluetooth` port; the planner filters these out so only network interfaces (`FastEthernet`, `GigabitEthernet`, `Serial`) receive IP configurations.
- **Fallback Guarantee**: Whenever a `.pkt` cannot be modified directly or if a user prefers manual configuration, the application generates a complete Cisco IOS CLI configuration script (`router_config.ios`) and CSV/Markdown address tables.

---

## How Each Part Works (Beginner's Guide)

### 1. Topology Discovery (`parser.py`)
Loads the `.pkt` file and creates a high-level representation of all devices, their physical ports, and links. It distinguishes between Layer 3 endpoints (Routers and PCs) and Layer 2 forwarders (Switches and Hubs).

### 2. Subnet & Broadcast Domain Detection (`subnet_detector.py`)
Starting from each router interface or end device, the engine performs a breadth-first search (BFS) traversing across cables and Layer 2 switches. Since switches forward frames without routing, all devices interconnected through switches form a single broadcast domain (Subnet). The connected router interface is automatically designated as the **Default Gateway**.

### 3. VLSM Address Planning (`vlsm.py`)
Variable Length Subnet Masking (VLSM) allows assigning subnets of different sizes to match exact device requirements:
1. Calculates needed host count: $\text{Needed} = \text{PCs} + \text{Gateways} + \text{Spare Padding}$.
2. Calculates minimum prefix length $P$: $2^{(32 - P)} - 2 \ge \text{Needed}$.
3. **Sorts subnets descending by size** (largest required hosts first). This prevents fragmentation of the base network.
4. Aligns each subnet to its block size boundary ($2^{32-P}$).
5. Allocates the first usable IP (`.1`) to the default gateway and subsequent IPs to hosts.

### 4. Configuration Assigner (`assigner.py`)
Writes the computed IP addresses into the `.pkt` object model:
- For end devices: uses `device.set_ip(address, gateway=gw)` to safely configure static IP, mask, and gateway simultaneously.
- For routers: configures interface addresses, applies `no shutdown`, and injects static routes.
- Adds ICMP Ping PDUs for quick verification in Packet Tracer.

### 5. Multi-Router Routing Engine (`routing.py`)
When multiple routers connect different subnets, directly connected interfaces are insufficient. The routing engine builds a graph between routers and calculates next-hop static routes (`ip route <dest_net> <dest_mask> <next_hop>`) so all LANs can communicate.

---

## Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Cisco Packet Tracer (optional, for opening and testing generated `.pkt` files)

### Install Dependencies
```bash
pip install -r requirements.txt
```

---

## How to Run the Application

### Option A: Visual Web Interface (Recommended for Beginners)
Start the web interface on localhost:
```bash
python run.py
```
Open your browser at: **`http://127.0.0.1:5000`**

1. Click **"Load 2-LANs Starter Example"** or upload your own `.pkt` file.
2. Enter your starting network address (e.g. `192.168.1.0/24`).
3. View the interactive network topology map and confirm the detected subnets.
4. Click **"Generate VLSM Plan"**.
5. Download your configured `.pkt` file, Cisco IOS scripts, or click **"Open in Cisco Packet Tracer"**!

### Option B: Command Line Interface (CLI)
Run headless from your terminal:
```bash
# Run on the built-in 2-LANs sample
python cli.py --sample 192.168.1.0/24 --non-interactive --export-ios router_config.ios --export-csv address_table.csv

# Run on your own Packet Tracer file
python cli.py my_network.pkt 10.0.0.0/16 -o my_network_configured.pkt --export-ios config.ios
```

---

## Testing Your Network in Packet Tracer

1. Open the generated `_configured.pkt` file in Cisco Packet Tracer.
2. Click on **PC1** &rarr; **Desktop** tab &rarr; **Command Prompt**.
3. Ping the default gateway:
   ```cmd
   ping 192.168.1.1
   ```
4. Ping across subnets to **PC3**:
   ```cmd
   ping 192.168.1.10
   ```
5. **Note for Beginners (ARP & STP Delay)**: The first ping may display `Request timed out`. This is normal behavior: switches run Spanning Tree Protocol (STP) which takes ~30 seconds to forward frames, and routers resolve MAC addresses via ARP. Press the **Fast Forward Time** button (`>>` at bottom toolbar) or re-run the ping command.

---

## Running the Automated Test Suite

Run the full pytest suite:
```bash
python -m pytest -v
```
All 15 unit and integration tests verify:
- VLSM mathematical calculations and block alignments
- Subnet boundary and gateway detection
- Address space exhaustion validation
- Duplicate address detection
- Multi-router static route generation
- End-to-end `.pkt` modification, non-destructive original file preservation, and reloading
- Web UI endpoints and file downloads
