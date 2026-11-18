"""Sample network topology generator: creates the 2-LANs starter example in .pkt format."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import pktlib


def create_two_lans_sample(
    output_unconfigured: str | os.PathLike[str],
    output_configured: str | os.PathLike[str] | None = None,
) -> Tuple[Path, Path | None]:
    """
    Builds the 2-LANs starter example network:
    - Router R1 connected to two switches SW1 and SW2
    - LAN 1: SW1 connected to PC1 and PC2
    - LAN 2: SW2 connected to PC3 and PC4
    
    Generates:
        1. An unconfigured file (devices & cables connected, no IPs)
        2. Optionally, a pre-configured reference file (IPs, gateways, pings set)
    """
    unconf_path = Path(output_unconfigured)
    unconf_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Build unconfigured network
    net = pktlib.new()

    r1 = net.router("R1", "1841+WIC-2T", at=(350, 160))
    sw1 = net.switch("SW1", at=(180, 290))
    sw2 = net.switch("SW2", at=(520, 290))

    pc1 = net.pc("PC1", at=(120, 420))
    pc2 = net.pc("PC2", at=(240, 420))
    pc3 = net.pc("PC3", at=(460, 420))
    pc4 = net.pc("PC4", at=(580, 420))

    # Connect LAN 1
    pc1["fa0"].connect(sw1["fa0/1"])
    pc2["fa0"].connect(sw1["fa0/2"])
    sw1["fa0/3"].connect(r1["fa0/0"])

    # Connect LAN 2
    pc3["fa0"].connect(sw2["fa0/1"])
    pc4["fa0"].connect(sw2["fa0/2"])
    sw2["fa0/3"].connect(r1["fa0/1"])

    net.save(unconf_path)

    conf_path = None
    if output_configured:
        conf_path = Path(output_configured)
        conf_path.parent.mkdir(parents=True, exist_ok=True)

        # Assign LAN 1 (192.168.1.0/25)
        r1["fa0/0"].address = "192.168.1.1/25"
        pc1.set_ip("192.168.1.2/25", gateway="192.168.1.1")
        pc2.set_ip("192.168.1.3/25", gateway="192.168.1.1")

        # Assign LAN 2 (192.168.1.128/25)
        r1["fa0/1"].address = "192.168.1.129/25"
        pc3.set_ip("192.168.1.130/25", gateway="192.168.1.129")
        pc4.set_ip("192.168.1.131/25", gateway="192.168.1.129")

        # Add ICMP Ping PDUs for Packet Tracer verification
        net.ping(pc1, pc3)
        net.ping(pc2, pc4)

        net.save(conf_path)

    return unconf_path, conf_path
