"""Parser module for reading Cisco Packet Tracer .pkt files and extracting topology data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pktlib
from pktlib._model import GUI_ONLY_KINDS

from .models import DeviceInfo, LinkInfo, NetworkTopology, PortInfo, ValidationIssue


def parse_pkt_file(file_path: str | os.PathLike[str]) -> Tuple[pktlib.Network, NetworkTopology]:
    """
    Parses a Cisco Packet Tracer .pkt file using pktlib (with strict=False for version compatibility).
    
    Returns:
        Tuple of (pktlib.Network, NetworkTopology)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Packet Tracer file not found: {path}")

    # Use strict=False to ensure compatibility with Packet Tracer 8.2.1, 8.2.2 and older builds
    try:
        net = pktlib.load(path, strict=False)
    except Exception as e:
        raise ValueError(f"Failed to open Packet Tracer file '{path.name}': {e}") from e

    devices: Dict[str, DeviceInfo] = {}
    issues: List[ValidationIssue] = []

    # 1. Parse Devices and Ports
    for dev in net.devices:
        kind = dev.kind
        model = getattr(dev, "model", kind)
        xy = getattr(dev, "xy", (0.0, 0.0))
        
        # Check device support
        is_supported = True
        support_note = None

        if kind in GUI_ONLY_KINDS:
            is_supported = False
            support_note = (
                f"{kind} ({model}) is configured via Packet Tracer GUI; "
                "pktlib cannot modify its IP configuration automatically."
            )
            issues.append(
                ValidationIssue(
                    severity="WARNING",
                    title=f"Unsupported Device Type: {dev.name}",
                    message=support_note,
                    affected_devices=[dev.name],
                )
            )
        elif kind == "IpPhone":
            is_supported = False
            support_note = "IP Phone configuration is not preserved by Packet Tracer offline config."
            issues.append(
                ValidationIssue(
                    severity="INFO",
                    title=f"Device Skipped: {dev.name}",
                    message=support_note,
                    affected_devices=[dev.name],
                )
            )

        dev_info = DeviceInfo(
            name=dev.name,
            kind=kind,
            model=model,
            x=float(xy[0]) if xy else 0.0,
            y=float(xy[1]) if xy else 0.0,
            is_supported=is_supported,
            support_note=support_note,
        )

        # Parse ports on device
        for port_name, port in dev.ports.items():
            # Check existing IP
            current_ip = port.ip if hasattr(port, "ip") and port.ip else None
            current_mask = port.mask if hasattr(port, "mask") and port.mask else None
            current_gw = None
            if dev_info.is_end_device:
                current_gw = getattr(dev, "gateway", None)

            access_vlan = getattr(port, "access_vlan", None)
            port_mode = getattr(port, "mode", None)

            p_info = PortInfo(
                device_name=dev.name,
                name=port_name,
                port_type=getattr(port, "type", "Ethernet"),
                is_connected=False,
                current_ip=current_ip,
                current_mask=current_mask,
                current_gw=current_gw,
                up=getattr(port, "up", True),
                access_vlan=int(access_vlan) if access_vlan is not None else None,
                port_mode=str(port_mode) if port_mode is not None else None,
            )
            dev_info.ports[port_name] = p_info

        # Parse SVIs if available
        if hasattr(dev, "interfaces") and dev.interfaces:
            for iname, iface in dev.interfaces.items():
                if iface and iface.address:
                    dev_info.svis[iname] = str(iface.address)

        # Parse running-config for switchport VLANs and SVIs as fallback
        if hasattr(dev, "running_config") and isinstance(dev.running_config, list):
            curr_iface = None
            for line in dev.running_config:
                line_str = line.strip()
                if line_str.startswith("interface "):
                    curr_iface = line_str.split()[1]
                elif curr_iface:
                    if curr_iface in dev_info.ports:
                        p = dev_info.ports[curr_iface]
                        if line_str.startswith("switchport access vlan "):
                            try:
                                p.access_vlan = int(line_str.split()[-1])
                            except ValueError:
                                pass
                        elif line_str.startswith("switchport mode "):
                            p.port_mode = line_str.split()[-1]
                    elif curr_iface.lower().startswith("vlan"):
                        if line_str.startswith("ip address "):
                            parts = line_str.split()
                            if len(parts) >= 4:
                                dev_info.svis[curr_iface] = f"{parts[2]} {parts[3]}"

        devices[dev.name] = dev_info

    # 2. Parse Links and update port peer relationships
    links: List[LinkInfo] = []
    for idx, link in enumerate(net.links):
        try:
            port_a, port_b = link.ports
            dev_a_name = port_a.device.name
            dev_b_name = port_b.device.name
            cable = getattr(link, "cable", "StraightThrough")

            # Update port info
            if dev_a_name in devices and port_a.name in devices[dev_a_name].ports:
                pa = devices[dev_a_name].ports[port_a.name]
                pa.is_connected = True
                pa.peer_device = dev_b_name
                pa.peer_port = port_b.name

            if dev_b_name in devices and port_b.name in devices[dev_b_name].ports:
                pb = devices[dev_b_name].ports[port_b.name]
                pb.is_connected = True
                pb.peer_device = dev_a_name
                pb.peer_port = port_a.name

            link_info = LinkInfo(
                id=f"link_{idx}",
                device_a=dev_a_name,
                port_a=port_a.name,
                device_b=dev_b_name,
                port_b=port_b.name,
                cable_type=str(cable),
            )
            links.append(link_info)
        except Exception as e:
            issues.append(
                ValidationIssue(
                    severity="WARNING",
                    title=f"Could not parse link #{idx}",
                    message=f"Error reading link: {e}",
                )
            )

    topology = NetworkTopology(
        filename=path.name,
        pt_version=getattr(net, "version", "Unknown"),
        devices=devices,
        links=links,
        subnets=[],
        issues=issues,
    )

    return net, topology
