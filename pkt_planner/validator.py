"""Validation module for address space, duplicate IPs, unsupported devices, and network structure."""

from __future__ import annotations

import ipaddress
from typing import Dict, List, Optional

from .models import NetworkTopology, SubnetBoundary, SubnetPlan, ValidationIssue


def validate_network_structure(
    topology: NetworkTopology,
    subnets: List[SubnetBoundary],
) -> List[ValidationIssue]:
    """
    Validates network topology structure for disconnected devices, unclear boundaries,
    and missing gateways.
    """
    issues: List[ValidationIssue] = []

    # 1. Disconnected Devices
    for dev_name, dev in topology.devices.items():
        if dev.is_end_device:
            connected = any(p.is_connected for p in dev.ports.values() if not p.is_bluetooth)
            if not connected:
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        title=f"Disconnected End Device: {dev_name}",
                        message=f"{dev.kind} '{dev_name}' has no connected network cables. It cannot receive an active IP assignment.",
                        affected_devices=[dev_name],
                    )
                )

    # 2. Subnets without Gateway
    for sub in subnets:
        if sub.status == "isolated" or not sub.gateway:
            issues.append(
                ValidationIssue(
                    severity="WARNING",
                    title=f"No Gateway for {sub.name}",
                    message=(
                        f"Subnet '{sub.name}' has {sub.host_count} device(s) but no router gateway interface. "
                        "Devices can only communicate within this local LAN segment."
                    ),
                    affected_devices=[m.device_name for m in sub.members],
                )
            )
        elif sub.status == "multi_gateway":
            issues.append(
                ValidationIssue(
                    severity="INFO",
                    title=f"Multiple Gateways in {sub.name}",
                    message=sub.notes,
                    affected_devices=[m.device_name for m in sub.members if m.role == "gateway"],
                )
            )

    return issues


def validate_address_space(
    base_cidr: str,
    subnets: List[SubnetBoundary],
) -> List[ValidationIssue]:
    """
    Validates whether the base network address space can satisfy the required subnets.
    """
    issues: List[ValidationIssue] = []

    if not base_cidr or not base_cidr.strip():
        issues.append(
            ValidationIssue(
                severity="ERROR",
                title="Missing Starting Network Address",
                message="Please provide a valid IPv4 network block, such as '192.168.1.0/24' or '10.0.0.0/16'.",
            )
        )
        return issues

    cidr_str = base_cidr.strip()
    if "/" not in cidr_str:
        cidr_str = f"{cidr_str}/24"

    try:
        base_net = ipaddress.IPv4Network(cidr_str, strict=False)
    except Exception as e:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                title="Invalid Base CIDR",
                message=f"'{base_cidr}' is not a valid IPv4 network: {e}",
            )
        )
        return issues

    total_base_addresses = base_net.num_addresses
    total_needed_hosts = sum(s.total_needed_hosts for s in subnets)

    if total_needed_hosts > total_base_addresses:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                title="Insufficient Address Space",
                message=(
                    f"The starting network {base_net.with_prefixlen} provides only {total_base_addresses} addresses, "
                    f"but your subnets require at least {total_needed_hosts} host addresses plus network/broadcast overhead. "
                    f"Consider expanding the address block (e.g. /{base_net.prefixlen - 1} or /{base_net.prefixlen - 2})."
                ),
            )
        )

    return issues


def validate_duplicate_addresses(plans: List[SubnetPlan]) -> List[ValidationIssue]:
    """
    Ensures that no duplicate IP addresses exist across all subnets and host assignments.
    """
    issues: List[ValidationIssue] = []
    seen_ips: Dict[str, str] = {}  # ip -> "DeviceName.Port"

    for plan in plans:
        # Check network & broadcast collisions
        net_addr = str(plan.network.network_address)
        bcast_addr = str(plan.network.broadcast_address)

        for a in plan.assignments:
            dev_port = f"{a.device_name}.{a.port_name}"

            if a.ip == net_addr:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        title=f"Network Address Conflict on {dev_port}",
                        message=f"Device {dev_port} was assigned the subnet network address {a.ip}.",
                        affected_devices=[a.device_name],
                    )
                )

            if a.ip == bcast_addr:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        title=f"Broadcast Address Conflict on {dev_port}",
                        message=f"Device {dev_port} was assigned the subnet broadcast address {a.ip}.",
                        affected_devices=[a.device_name],
                    )
                )

            if a.ip in seen_ips:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        title=f"Duplicate IP Address Detected: {a.ip}",
                        message=f"IP {a.ip} is assigned to both {seen_ips[a.ip]} and {dev_port}.",
                        affected_devices=[a.device_name, seen_ips[a.ip].split(".")[0]],
                    )
                )
            else:
                seen_ips[a.ip] = dev_port

    return issues


def run_full_validation(
    topology: NetworkTopology,
    base_cidr: str,
    subnets: List[SubnetBoundary],
    plans: Optional[List[SubnetPlan]] = None,
) -> List[ValidationIssue]:
    """
    Runs all validation checks on the topology, subnet definitions, address space, and assignments.
    """
    all_issues: List[ValidationIssue] = []

    # Structure validation
    all_issues.extend(validate_network_structure(topology, subnets))

    # Address space validation
    all_issues.extend(validate_address_space(base_cidr, subnets))

    # If plans are already calculated, validate assignments
    if plans:
        all_issues.extend(validate_duplicate_addresses(plans))

    # Sort issues: ERROR first, then WARNING, then INFO
    severity_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    all_issues.sort(key=lambda x: severity_order.get(x.severity, 3))

    return all_issues
