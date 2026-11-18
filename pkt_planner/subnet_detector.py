"""Subnet and broadcast domain boundary detection algorithm for network topologies."""

from __future__ import annotations

import re
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from .models import DeviceInfo, NetworkTopology, PortRef, SubnetBoundary, SubnetMember, ValidationIssue


def extract_vlan_id(name: str) -> Optional[int]:
    """Extracts numeric VLAN ID from an interface name (e.g. Vlan10, Fa0/0.20, vlan 30)."""
    m = re.search(r'(?:vlan|\.)\s*(\d+)', name, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def detect_subnets(topology: NetworkTopology) -> Tuple[List[SubnetBoundary], List[ValidationIssue]]:
    """
    Detects subnets (broadcast domains) across the network topology.
    
    Supports:
    - VLAN-segmented domains with MultiLayerSwitch SVIs, router sub-interfaces, and switch access ports.
    - Traditional flat Layer 2 networks with routers and switches.
    - Point-to-point WAN links between routers.
    - Isolated local networks without routers.
    """
    devices = topology.devices
    subnets: List[SubnetBoundary] = []
    issues: List[ValidationIssue] = []

    # Map each (device, port) to its connected peer (device, port)
    peer_map: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for link in topology.links:
        peer_map[(link.device_a, link.port_a)] = (link.device_b, link.port_b)
        peer_map[(link.device_b, link.port_b)] = (link.device_a, link.port_a)

    # Check for disconnected end devices
    for dev_name, dev in devices.items():
        if dev.is_end_device:
            connected_ports = [p for p in dev.ports.values() if not p.is_bluetooth and p.is_connected]
            if not connected_ports:
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        title=f"Disconnected Device: {dev_name}",
                        message=f"{dev.kind} '{dev_name}' has no connected network cables.",
                        affected_devices=[dev_name],
                    )
                )

    covered_ports: Set[Tuple[str, str]] = set()
    covered_svis: Set[Tuple[str, str]] = set()
    subnet_idx = 1

    # Check for VLAN presence across switches, SVIs, and routers
    vlan_ids: Set[int] = set()
    for d in devices.values():
        if d.is_switch:
            for p in d.ports.values():
                if p.access_vlan is not None and p.access_vlan > 0:
                    vlan_ids.add(p.access_vlan)
        for s in d.svis:
            vid = extract_vlan_id(s)
            if vid is not None and vid > 0:
                vlan_ids.add(vid)
        if d.is_router:
            for p in d.ports.values():
                vid = extract_vlan_id(p.name)
                if vid is not None and vid > 0:
                    vlan_ids.add(vid)

    # 1. Process VLAN subnets if any exist
    if vlan_ids:
        for vid in sorted(vlan_ids):
            members: List[SubnetMember] = []
            gateway: Optional[PortRef] = None

            # Look for Gateway in MLS SVIs
            for d in devices.values():
                if d.is_l3_gateway:
                    for s in d.svis:
                        if extract_vlan_id(s) == vid:
                            gateway = PortRef(d.name, s)
                            members.append(SubnetMember(d.name, s, d.kind, role="gateway"))
                            covered_svis.add((d.name, s))
                            break
                    if gateway:
                        break

            # If no MLS SVI, check router sub-interfaces
            if not gateway:
                for d in devices.values():
                    if d.is_router:
                        for p in d.ports.values():
                            if extract_vlan_id(p.name) == vid:
                                gateway = PortRef(d.name, p.name)
                                members.append(SubnetMember(d.name, p.name, d.kind, role="gateway"))
                                covered_ports.add((d.name, p.name))
                                break
                        if gateway:
                            break

            # If still no gateway, check router connected to an access port in this VLAN
            if not gateway:
                for d in devices.values():
                    if d.is_router:
                        for p in d.ports.values():
                            peer = peer_map.get((d.name, p.name))
                            if peer:
                                sw_name, sw_p = peer
                                if sw_name in devices and devices[sw_name].is_switch:
                                    if devices[sw_name].ports.get(sw_p) and devices[sw_name].ports[sw_p].access_vlan == vid:
                                        gateway = PortRef(d.name, p.name)
                                        members.append(SubnetMember(d.name, p.name, d.kind, role="gateway"))
                                        covered_ports.add((d.name, p.name))
                                        break
                        if gateway:
                            break

            # Collect End Devices on this VLAN
            for d in devices.values():
                if d.is_end_device:
                    for p in d.ports.values():
                        if p.is_bluetooth or not p.is_connected:
                            continue
                        peer = peer_map.get((d.name, p.name))
                        if peer:
                            sw_name, sw_p = peer
                            if sw_name in devices and devices[sw_name].is_switch:
                                sw_port = devices[sw_name].ports.get(sw_p)
                                if sw_port and sw_port.access_vlan == vid:
                                    members.append(SubnetMember(d.name, p.name, d.kind, role="host"))
                                    covered_ports.add((d.name, p.name))

            # Collect Switch SVIs on this VLAN (e.g. management VLAN 99)
            for d in devices.values():
                if d.kind == "Switch":
                    for s in d.svis:
                        if extract_vlan_id(s) == vid:
                            members.append(SubnetMember(d.name, s, d.kind, role="host"))
                            covered_svis.add((d.name, s))

            if members:
                status = "detected" if gateway else "isolated"
                gw_desc = f"{gateway.device} {gateway.port}" if gateway else "Isolated"
                sub_name = f"VLAN {vid} ({gw_desc})"
                notes = f"VLAN {vid} broadcast domain with gateway {gw_desc}."
                if not gateway:
                    issues.append(
                        ValidationIssue(
                            severity="WARNING",
                            title=f"Isolated VLAN Without Gateway (VLAN {vid})",
                            message=f"No Layer 3 gateway detected for VLAN {vid}.",
                            affected_devices=[m.device_name for m in members],
                        )
                    )

                subnets.append(
                    SubnetBoundary(
                        subnet_id=f"subnet_{subnet_idx}",
                        name=sub_name,
                        vlan_id=vid,
                        gateway=gateway,
                        members=members,
                        host_count=len(members),
                        padding=0,
                        status=status,
                        notes=notes,
                    )
                )
                subnet_idx += 1

    # 2. Standard L2 BFS for remaining devices / non-VLAN broadcast domains
    l3_ports: List[Tuple[str, str]] = []
    for d_name, d in devices.items():
        if d.is_router or d.is_end_device:
            for p_name, p in d.ports.items():
                if p.is_bluetooth:
                    continue
                if p.is_connected and (d_name, p_name) not in covered_ports:
                    l3_ports.append((d_name, p_name))

    visited_l3_ports: Set[Tuple[str, str]] = set()

    for start_l3 in l3_ports:
        if start_l3 in visited_l3_ports:
            continue

        domain_l3_ports: Set[Tuple[str, str]] = set()
        visited_switches: Set[str] = set()
        queue = deque([start_l3])

        while queue:
            curr_dev_name, curr_port_name = queue.popleft()

            peer = peer_map.get((curr_dev_name, curr_port_name))
            if not peer:
                continue

            peer_dev_name, peer_port_name = peer
            peer_dev = devices.get(peer_dev_name)
            if not peer_dev:
                continue

            if peer_dev.is_router or peer_dev.is_end_device:
                if (peer_dev_name, peer_port_name) not in covered_ports:
                    domain_l3_ports.add((peer_dev_name, peer_port_name))
                    visited_l3_ports.add((peer_dev_name, peer_port_name))
            elif peer_dev.is_switch:
                if peer_dev_name not in visited_switches:
                    visited_switches.add(peer_dev_name)
                    for sw_port_name, sw_port in peer_dev.ports.items():
                        if sw_port_name != peer_port_name and sw_port.is_connected:
                            queue.append((peer_dev_name, sw_port_name))

        domain_l3_ports.add(start_l3)
        visited_l3_ports.add(start_l3)

        routers: List[Tuple[str, str]] = []
        hosts: List[Tuple[str, str]] = []

        for d_name, p_name in sorted(domain_l3_ports):
            dev = devices[d_name]
            if dev.is_router:
                routers.append((d_name, p_name))
            elif dev.is_end_device:
                hosts.append((d_name, p_name))

        members = []
        gateway = None
        status = "detected"
        notes = ""

        if len(routers) == 1:
            gw_dev, gw_port = routers[0]
            gateway = PortRef(gw_dev, gw_port)
            members.append(SubnetMember(gw_dev, gw_port, devices[gw_dev].kind, role="gateway"))
            for h_dev, h_port in hosts:
                members.append(SubnetMember(h_dev, h_port, devices[h_dev].kind, role="host"))
            subnet_name = f"LAN {subnet_idx} ({gw_dev} {gw_port})"
            notes = f"Standard LAN with default gateway on {gw_dev} {gw_port}."

        elif len(routers) == 2 and len(hosts) == 0:
            r1_dev, r1_port = routers[0]
            r2_dev, r2_port = routers[1]
            gateway = PortRef(r1_dev, r1_port)
            members.append(SubnetMember(r1_dev, r1_port, "Router", role="gateway"))
            members.append(SubnetMember(r2_dev, r2_port, "Router", role="transit"))
            subnet_name = f"WAN Link ({r1_dev}-{r2_dev})"
            status = "detected"
            notes = f"Point-to-point router link between {r1_dev} ({r1_port}) and {r2_dev} ({r2_port})."

        elif len(routers) > 1 and len(hosts) > 0:
            gw_dev, gw_port = routers[0]
            gateway = PortRef(gw_dev, gw_port)
            members.append(SubnetMember(gw_dev, gw_port, devices[gw_dev].kind, role="gateway"))
            for r_dev, r_port in routers[1:]:
                members.append(SubnetMember(r_dev, r_port, devices[r_dev].kind, role="gateway"))
            for h_dev, h_port in hosts:
                members.append(SubnetMember(h_dev, h_port, devices[h_dev].kind, role="host"))
            subnet_name = f"Shared LAN {subnet_idx}"
            status = "multi_gateway"
            notes = (
                f"Multiple router interfaces detected ({', '.join(f'{d}.{p}' for d, p in routers)}). "
                f"Designated {gw_dev}.{gw_port} as primary gateway; please confirm or adjust."
            )
            issues.append(
                ValidationIssue(
                    severity="INFO",
                    title=f"Multiple Gateways in Subnet {subnet_idx}",
                    message=notes,
                    affected_devices=[d for d, _ in routers],
                )
            )

        else:
            for h_dev, h_port in hosts:
                members.append(SubnetMember(h_dev, h_port, devices[h_dev].kind, role="host"))
            subnet_name = f"Isolated LAN {subnet_idx}"
            status = "isolated"
            notes = "No router interface detected in this broadcast domain. Devices can communicate only within this local LAN."
            issues.append(
                ValidationIssue(
                    severity="WARNING",
                    title=f"Isolated Subnet Without Gateway ({subnet_name})",
                    message=notes,
                    affected_devices=[d for d, _ in hosts],
                )
            )

        host_count = len(members)
        subnet = SubnetBoundary(
            subnet_id=f"subnet_{subnet_idx}",
            name=subnet_name,
            gateway=gateway,
            members=members,
            host_count=host_count,
            padding=0,
            status=status,
            notes=notes,
        )
        subnets.append(subnet)
        subnet_idx += 1

    topology.subnets = subnets
    topology.issues.extend(issues)
    return subnets, issues
