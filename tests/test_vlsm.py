"""Unit tests for VLSM calculation and address planning engine."""

import ipaddress
import pytest

from pkt_planner.models import PortRef, SubnetBoundary, SubnetMember
from pkt_planner.vlsm import (
    InsufficientAddressSpaceError,
    get_prefix_for_hosts,
    plan_vlsm_subnets,
)


def test_prefix_calculation():
    # 2 hosts (point-to-point) -> /30 (4 addresses, 2 usable)
    assert get_prefix_for_hosts(2) == 30
    # 5 hosts -> /29 (8 addresses, 6 usable)
    assert get_prefix_for_hosts(5) == 29
    # 6 hosts -> /29 (6 usable)
    assert get_prefix_for_hosts(6) == 29
    # 7 hosts -> /28 (16 addresses, 14 usable)
    assert get_prefix_for_hosts(7) == 28
    # 30 hosts -> /27 (32 addresses, 30 usable)
    assert get_prefix_for_hosts(30) == 27
    # 50 hosts -> /26 (64 addresses, 62 usable)
    assert get_prefix_for_hosts(50) == 26
    # 100 hosts -> /25 (128 addresses, 126 usable)
    assert get_prefix_for_hosts(100) == 25


def test_vlsm_non_overlapping_subnets():
    # LAN1: 25 hosts, LAN2: 10 hosts, WAN1: 2 hosts
    subnets = [
        SubnetBoundary(
            subnet_id="sub_1",
            name="LAN 1",
            gateway=PortRef("R1", "Fa0/0"),
            members=[SubnetMember("R1", "Fa0/0", "Router", "gateway")] + [
                SubnetMember(f"PC{i}", "Fa0", "Pc", "host") for i in range(1, 26)
            ],
            host_count=26,
        ),
        SubnetBoundary(
            subnet_id="sub_2",
            name="LAN 2",
            gateway=PortRef("R1", "Fa0/1"),
            members=[SubnetMember("R1", "Fa0/1", "Router", "gateway")] + [
                SubnetMember(f"PC{i}", "Fa0", "Pc", "host") for i in range(26, 36)
            ],
            host_count=11,
        ),
        SubnetBoundary(
            subnet_id="sub_3",
            name="WAN 1",
            gateway=PortRef("R1", "Se0/0/0"),
            members=[
                SubnetMember("R1", "Se0/0/0", "Router", "gateway"),
                SubnetMember("R2", "Se0/0/0", "Router", "transit"),
            ],
            host_count=2,
        ),
    ]

    plans = plan_vlsm_subnets("192.168.1.0/24", subnets)
    assert len(plans) == 3

    # Check non-overlapping networks
    networks = [p.network for p in plans]
    for i in range(len(networks)):
        for j in range(i + 1, len(networks)):
            assert not networks[i].overlaps(networks[j]), f"Overlapping subnets: {networks[i]} and {networks[j]}"

    # Verify assignments
    all_assigned_ips = set()
    for p in plans:
        for a in p.assignments:
            # IP must be within subnet
            assert ipaddress.IPv4Address(a.ip) in p.network
            # No duplicate IPs
            assert a.ip not in all_assigned_ips, f"Duplicate IP: {a.ip}"
            all_assigned_ips.add(a.ip)
            # Host gateway must be within subnet
            if a.gateway:
                assert ipaddress.IPv4Address(a.gateway) in p.network


def test_insufficient_address_space():
    # Base network is /28 (16 addresses total, 14 usable)
    # Trying to allocate 50 hosts should fail
    subnets = [
        SubnetBoundary(
            subnet_id="sub_large",
            name="Large LAN",
            gateway=PortRef("R1", "Fa0/0"),
            members=[SubnetMember("R1", "Fa0/0", "Router", "gateway")] + [
                SubnetMember(f"PC{i}", "Fa0", "Pc", "host") for i in range(50)
            ],
            host_count=51,
        )
    ]

    with pytest.raises(InsufficientAddressSpaceError):
        plan_vlsm_subnets("192.168.1.0/28", subnets)


def test_invalid_base_cidr():
    subnets = [SubnetBoundary(subnet_id="sub1", name="Test LAN", host_count=4)]
    with pytest.raises(ValueError):
        plan_vlsm_subnets("invalid-ip", subnets)
    with pytest.raises(ValueError):
        plan_vlsm_subnets("", subnets)
