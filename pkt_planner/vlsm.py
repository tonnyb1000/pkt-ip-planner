"""VLSM (Variable Length Subnet Masking) planning and address assignment engine."""

from __future__ import annotations

import ipaddress
from typing import Dict, List, Tuple

from .models import HostAssignment, SubnetBoundary, SubnetPlan


class InsufficientAddressSpaceError(Exception):
    """Raised when the base network cannot accommodate the requested subnets."""
    pass


def get_prefix_for_hosts(needed_hosts: int) -> int:
    """
    Calculates the smallest IPv4 prefix (largest subnet) capable of hosting the needed number of hosts.
    
    Formula: 2^(32 - P) - 2 >= needed_hosts
    Standard minimum subnet is /30 (2 usable hosts).
    """
    needed = max(needed_hosts, 2)
    for p in range(30, 0, -1):
        usable = (2 ** (32 - p)) - 2
        if usable >= needed:
            return p
    raise ValueError(f"Requested host count ({needed_hosts}) exceeds IPv4 addressing limits!")


def plan_vlsm_subnets(
    base_cidr: str,
    subnets: List[SubnetBoundary],
    gateway_first: bool = True,
) -> List[SubnetPlan]:
    """
    Generates non-overlapping subnets using VLSM from a base CIDR block.
    
    Args:
        base_cidr: The starting network address, e.g. "192.168.1.0/24"
        subnets: List of SubnetBoundary objects detected from the topology
        gateway_first: If True, assigns .1 to the gateway and subsequent IPs to hosts
        
    Returns:
        List of SubnetPlan objects with assigned IP addresses and host mappings
        
    Raises:
        InsufficientAddressSpaceError: If the base network is too small for the required subnets
        ValueError: If base_cidr is invalid
    """
    if not base_cidr or not base_cidr.strip():
        raise ValueError("Starting network address cannot be empty.")

    cidr_str = base_cidr.strip()
    if "/" not in cidr_str:
        # Default to /24 if user omitted prefix
        cidr_str = f"{cidr_str}/24"

    try:
        base_network = ipaddress.IPv4Network(cidr_str, strict=False)
    except Exception as e:
        raise ValueError(f"Invalid starting network address '{base_cidr}': {e}") from e

    if not subnets:
        return []

    # Sort subnets descending by required hosts (essential VLSM rule to prevent address fragmentation)
    sorted_subnets = sorted(subnets, key=lambda s: s.total_needed_hosts, reverse=True)

    plans: List[SubnetPlan] = []
    current_addr = int(base_network.network_address)
    max_addr = int(base_network.broadcast_address)
    assigned_ips_global: Dict[str, str] = {}

    for subnet in sorted_subnets:
        needed = subnet.total_needed_hosts
        prefix = get_prefix_for_hosts(needed)
        block_size = 2 ** (32 - prefix)

        # Align current address to block size boundary
        if current_addr % block_size != 0:
            current_addr += block_size - (current_addr % block_size)

        subnet_end = current_addr + block_size - 1

        if subnet_end > max_addr:
            total_usable_base = base_network.num_addresses - 2
            total_needed = sum(s.total_needed_hosts for s in subnets)
            raise InsufficientAddressSpaceError(
                f"Insufficient address space in base network {base_network.with_prefixlen}! "
                f"Cannot allocate '{subnet.name}' (needs {needed} hosts, prefix /{prefix}, block size {block_size}). "
                f"Total usable base addresses: {total_usable_base}, Total hosts needed: {total_needed}. "
                f"Please provide a larger network block (e.g. /{base_network.prefixlen - 1} or /{base_network.prefixlen - 2})."
            )

        allocated_net = ipaddress.IPv4Network((current_addr, prefix))
        netmask_str = str(allocated_net.netmask)
        broadcast_str = str(allocated_net.broadcast_address)
        usable_hosts = list(allocated_net.hosts())

        if not usable_hosts:
            raise InsufficientAddressSpaceError(f"Subnet {allocated_net} has no usable host addresses.")

        first_usable = str(usable_hosts[0])
        last_usable = str(usable_hosts[-1])

        # Assign Gateway and Host IPs
        assignments: List[HostAssignment] = []
        host_ip_index = 0

        # Separate gateway members and host members
        gateway_members = [m for m in subnet.members if m.role == "gateway"]
        host_members = [m for m in subnet.members if m.role != "gateway"]

        # Default gateway IP for hosts (defaults to first usable host address)
        gw_ip_str = first_usable

        if gateway_first and gateway_members:
            for gm in gateway_members:
                if host_ip_index >= len(usable_hosts):
                    raise InsufficientAddressSpaceError(f"Subnet {allocated_net} ran out of usable IP addresses.")
                ip_val = str(usable_hosts[host_ip_index])
                host_ip_index += 1
                gw_ip_str = ip_val
                assignment = HostAssignment(
                    device_name=gm.device_name,
                    port_name=gm.port_name,
                    device_kind=gm.device_kind,
                    ip=ip_val,
                    netmask=netmask_str,
                    cidr=f"{ip_val}/{prefix}",
                    gateway=ip_val,  # Router interface is its own gateway
                    role="gateway",
                )
                assignments.append(assignment)
                assigned_ips_global[ip_val] = f"{gm.device_name}.{gm.port_name}"

        # Assign IPs to host members
        for hm in host_members:
            if host_ip_index >= len(usable_hosts):
                raise InsufficientAddressSpaceError(
                    f"Subnet {allocated_net} ran out of usable host addresses for {hm.device_name}."
                )
            ip_val = str(usable_hosts[host_ip_index])
            host_ip_index += 1
            assignment = HostAssignment(
                device_name=hm.device_name,
                port_name=hm.port_name,
                device_kind=hm.device_kind,
                ip=ip_val,
                netmask=netmask_str,
                cidr=f"{ip_val}/{prefix}",
                gateway=gw_ip_str,
                role=hm.role,
            )
            assignments.append(assignment)
            assigned_ips_global[ip_val] = f"{hm.device_name}.{hm.port_name}"

        plan = SubnetPlan(
            subnet_id=subnet.subnet_id,
            name=subnet.name,
            network=allocated_net,
            prefix=prefix,
            netmask=netmask_str,
            broadcast=broadcast_str,
            gateway_ip=gw_ip_str,
            usable_range=(first_usable, last_usable),
            needed_hosts=needed,
            allocated_hosts=allocated_net.num_addresses - 2,
            assignments=assignments,
        )
        plans.append(plan)

        # Advance pointer
        current_addr += block_size

    # Sort plans back into original subnet_id order for clean presentation
    id_order = {s.subnet_id: i for i, s in enumerate(subnets)}
    plans.sort(key=lambda p: id_order.get(p.subnet_id, 0))

    return plans
