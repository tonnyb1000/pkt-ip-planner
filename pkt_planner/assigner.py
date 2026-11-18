"""Assigner module: modifies Packet Tracer network objects and writes updated .pkt files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pktlib

import xml.etree.ElementTree as ET


def _configure_end_device_static_ip(
    dev: pktlib.Device,
    port_name: str,
    ip: str,
    netmask: str,
    gateway: str,
    prefix: int,
) -> None:
    """
    Configures static IP on an end device (PC, Laptop, Server, Printer),
    ensuring Cisco Packet Tracer GUI loads with static IP populated and DHCP disabled.
    """
    # 1. Update internal pktlib device properties if possible
    try:
        dev.set_ip(
            address=f"{ip}/{prefix}",
            gateway=gateway,
            port=port_name,
        )
    except Exception:
        pass

    # 2. Update port XML elements
    try:
        port = dev[port_name]
        port_el = port.el

        tag_values = [
            ("IP", ip),
            ("SUBNET", netmask),
            ("PORT_GATEWAY", gateway),
            ("PORT_DHCP_ENABLE", "false"),
            ("UP_METHOD", "5"),
        ]
        for tag, val in tag_values:
            el = port_el.find(tag)
            if el is None:
                el = ET.SubElement(port_el, tag)
            el.text = val

        try:
            port.ip = ip
            port.mask = netmask
        except Exception:
            pass
    except Exception:
        pass

    # 3. Update device ENGINE gateway
    eng = dev.el.find("ENGINE")
    if eng is not None:
        gw_el = eng.find("GATEWAY")
        if gw_el is None:
            gw_el = ET.SubElement(eng, "GATEWAY")
        gw_el.text = gateway

    # 4. Crucial: Remove port from DHCP_CLIENT/PORT_DATA_MAP to prevent PT resetting to DHCP mode on load
    dhcp_map = dev.el.find(".//DHCP_CLIENT/PORT_DATA_MAP")
    if dhcp_map is not None:
        for entry in list(dhcp_map.findall("PORT_DATA_ENTRY")):
            p_tag = entry.find("PORT")
            if p_tag is not None and (p_tag.text == port_name or "ethernet" in (p_tag.text or "").lower()):
                dhcp_map.remove(entry)


def _update_svi_in_configs(
    dev: pktlib.Device,
    vlan_name: str,
    ip: str,
    netmask: str,
    network_addr: Optional[str] = None,
    gateway: Optional[str] = None,
) -> bool:
    """Updates SVI interface IP and DHCP pool (if any) in Cisco IOS running and startup configs."""
    updated = False
    for tag in ["RUNNINGCONFIG", "STARTUPCONFIG"]:
        cfg = dev.el.find(f".//{tag}")
        if cfg is None:
            continue
        lines = list(cfg.findall("LINE"))
        for i, line_el in enumerate(lines):
            text = (line_el.text or "").strip()
            if text.lower() == f"interface {vlan_name}".lower():
                ip_found = False
                for j in range(i + 1, min(i + 15, len(lines))):
                    sub_text = (lines[j].text or "").strip()
                    if sub_text.startswith("ip address "):
                        lines[j].text = f" ip address {ip} {netmask}"
                        ip_found = True
                        updated = True
                        break
                    elif sub_text == "!" or sub_text.startswith("interface "):
                        break
                if not ip_found:
                    new_line = ET.Element("LINE")
                    new_line.text = f" ip address {ip} {netmask}"
                    idx = list(cfg).index(line_el)
                    cfg.insert(idx + 1, new_line)
                    updated = True

            # Also update DHCP pool if configured for this subnet
            if network_addr and text.startswith("ip dhcp pool "):
                for j in range(i + 1, min(i + 10, len(lines))):
                    sub_text = (lines[j].text or "").strip()
                    if sub_text.startswith("network "):
                        lines[j].text = f" network {network_addr} {netmask}"
                    elif sub_text.startswith("default-router "):
                        lines[j].text = f" default-router {gateway or ip}"
                    elif sub_text == "!" or sub_text.startswith("ip dhcp pool ") or sub_text.startswith("interface "):
                        break

    return updated


def _update_subinterface_in_configs(dev: pktlib.Device, subif_name: str, ip: str, netmask: str) -> bool:
    """Updates router sub-interface IP in Cisco IOS running and startup configs."""
    updated = False
    for tag in ["RUNNINGCONFIG", "STARTUPCONFIG"]:
        cfg = dev.el.find(f".//{tag}")
        if cfg is None:
            continue
        lines = list(cfg.findall("LINE"))
        for i, line_el in enumerate(lines):
            text = (line_el.text or "").strip()
            if text.lower() == f"interface {subif_name}".lower():
                for j in range(i + 1, min(i + 15, len(lines))):
                    sub_text = (lines[j].text or "").strip()
                    if sub_text.startswith("ip address "):
                        lines[j].text = f" ip address {ip} {netmask}"
                        updated = True
                        break
                    elif sub_text == "!" or sub_text.startswith("interface "):
                        break
    return updated


def apply_plan_to_network(
    source_pkt_path: str | os.PathLike[str],
    output_pkt_path: str | os.PathLike[str],
    plans: List[SubnetPlan],
    static_routes: Optional[Dict[str, List[StaticRoute]]] = None,
    add_test_pings: bool = True,
) -> Tuple[bool, str]:
    """
    Applies the subnet IP plan and static routes to a Packet Tracer network file,
    saving the result to output_pkt_path while keeping the source file unchanged.
    
    Returns:
        Tuple of (success: bool, status_message: str)
    """
    src_path = Path(source_pkt_path)
    out_path = Path(output_pkt_path)

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    if src_path.resolve() == out_path.resolve():
        raise ValueError("Output file must be different from the source file to preserve the original file.")

    # Always use strict=False for broader version compatibility (Packet Tracer 8.2.0, 8.2.1, 8.2.2, etc.)
    net = pktlib.load(src_path, strict=False)

    assigned_count = 0
    route_count = 0

    # 1. Apply IP addresses to all devices
    for plan in plans:
        for a in plan.assignments:
            try:
                dev = net.device(a.device_name)
            except Exception as e:
                return False, f"Device '{a.device_name}' not found in network: {e}"

            # SVI interfaces on MultiLayerSwitch, Switch, or Router (e.g. Vlan10, Vlan20, Vlan99)
            if a.port_name.lower().startswith("vlan"):
                try:
                    _update_svi_in_configs(
                        dev,
                        a.port_name,
                        a.ip,
                        a.netmask,
                        str(plan.network.network_address),
                        a.gateway,
                    )
                    assigned_count += 1
                except Exception as e:
                    return False, f"Failed to configure SVI on {a.device_name} ({a.port_name}): {e}"

            # Router physical or sub-interfaces
            elif a.device_kind == "Router" or dev.kind == "Router":
                try:
                    if "." in a.port_name:
                        _update_subinterface_in_configs(dev, a.port_name, a.ip, a.netmask)
                    else:
                        port = dev[a.port_name]
                        port.address = f"{a.ip}/{plan.prefix}"
                    assigned_count += 1
                except Exception as e:
                    return False, f"Failed to assign IP to Router {a.device_name} port {a.port_name}: {e}"

            # MultiLayerSwitch routed physical ports
            elif a.device_kind == "MultiLayerSwitch" or dev.kind == "MultiLayerSwitch":
                try:
                    port = dev[a.port_name]
                    port.address = f"{a.ip}/{plan.prefix}"
                    assigned_count += 1
                except Exception as e:
                    return False, f"Failed to assign IP to MLS {a.device_name} port {a.port_name}: {e}"

            # End devices (PC, Laptop, Server, Printer)
            else:
                try:
                    _configure_end_device_static_ip(
                        dev=dev,
                        port_name=a.port_name,
                        ip=a.ip,
                        netmask=a.netmask,
                        gateway=a.gateway,
                        prefix=plan.prefix,
                    )
                    assigned_count += 1
                except Exception as e:
                    return False, f"Failed to configure IP on {a.device_name} ({a.port_name}): {e}"

    # 2. Apply static routes on routers if multi-router network
    if static_routes:
        for r_name, routes in static_routes.items():
            if not routes:
                continue
            try:
                dev = net.device(r_name)
                cmds = [r.ios_command for r in routes]
                dev.config(cmds)
                route_count += len(cmds)
            except Exception as e:
                # If static route config encounters an issue, return error
                return False, f"Failed to apply static routes on router {r_name}: {e}"

    # 3. Add test ping PDUs between subnets for quick verification in Packet Tracer
    if add_test_pings:
        # Collect one end device from each subnet that has hosts
        subnet_hosts: List[Tuple[str, str]] = []  # (subnet_id, host_device_name)
        for plan in plans:
            host_assignments = [a for a in plan.assignments if a.role == "host"]
            if host_assignments:
                subnet_hosts.append((plan.subnet_id, host_assignments[0].device_name))

        # Add pings between different subnets
        for i in range(len(subnet_hosts)):
            for j in range(i + 1, min(len(subnet_hosts), i + 3)):  # Limit to 2 pings per subnet to keep PDU list clean
                src_dev = subnet_hosts[i][1]
                dst_dev = subnet_hosts[j][1]
                try:
                    net.ping(src_dev, dst_dev)
                except Exception:
                    # Non-fatal if ping PDU fails
                    pass

    # 4. Save to output path
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        net.save(out_path)
    except Exception as e:
        return False, f"Failed to save output file '{out_path}': {e}"

    msg = (
        f"Successfully generated '{out_path.name}'. "
        f"Configured {assigned_count} interface IP addresses, "
        f"{route_count} static routes across {len(plans)} subnets. "
        f"Original file '{src_path.name}' remains unchanged."
    )
    return True, msg
