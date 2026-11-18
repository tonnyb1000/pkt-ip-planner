"""Unit tests for validation of address space, duplicate IPs, and network structure."""

import ipaddress
from pkt_planner.models import (
    DeviceInfo,
    HostAssignment,
    NetworkTopology,
    PortInfo,
    PortRef,
    SubnetBoundary,
    SubnetMember,
    SubnetPlan,
)
from pkt_planner.validator import (
    run_full_validation,
    validate_address_space,
    validate_duplicate_addresses,
    validate_network_structure,
)


def test_validate_address_space_ok():
    subnets = [
        SubnetBoundary("s1", "LAN 1", host_count=10),
        SubnetBoundary("s2", "LAN 2", host_count=10),
    ]
    issues = validate_address_space("192.168.1.0/24", subnets)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 0


def test_validate_address_space_insufficient():
    # 300 hosts needed, /24 only has 256 addresses
    subnets = [
        SubnetBoundary("s1", "LAN 1", host_count=200),
        SubnetBoundary("s2", "LAN 2", host_count=100),
    ]
    issues = validate_address_space("192.168.1.0/24", subnets)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 1
    assert "Insufficient Address Space" in errors[0].title


def test_validate_duplicate_addresses_detected():
    net = ipaddress.IPv4Network("192.168.1.0/24")
    # Duplicate IP assigned to PC1 and PC2
    plans = [
        SubnetPlan(
            subnet_id="s1",
            name="LAN 1",
            network=net,
            prefix=24,
            netmask="255.255.255.0",
            broadcast="192.168.1.255",
            gateway_ip="192.168.1.1",
            usable_range=("192.168.1.1", "192.168.1.254"),
            needed_hosts=3,
            allocated_hosts=254,
            assignments=[
                HostAssignment("R1", "Fa0/0", "Router", "192.168.1.1", "255.255.255.0", "192.168.1.1/24", "192.168.1.1", "gateway"),
                HostAssignment("PC1", "Fa0", "Pc", "192.168.1.2", "255.255.255.0", "192.168.1.2/24", "192.168.1.1", "host"),
                HostAssignment("PC2", "Fa0", "Pc", "192.168.1.2", "255.255.255.0", "192.168.1.2/24", "192.168.1.1", "host"),  # Duplicate!
            ],
        )
    ]
    issues = validate_duplicate_addresses(plans)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 1
    assert "Duplicate IP Address Detected" in errors[0].title
    assert "192.168.1.2" in errors[0].message


def test_validate_disconnected_devices():
    devices = {
        "PC1": DeviceInfo(
            name="PC1",
            kind="Pc",
            model="PC-PT",
            ports={"Fa0": PortInfo("PC1", "Fa0", is_connected=False)},  # Disconnected!
        )
    }
    topology = NetworkTopology(
        filename="test.pkt",
        pt_version="8.2.0",
        devices=devices,
        links=[],
        subnets=[],
        issues=[],
    )
    issues = validate_network_structure(topology, [])
    warnings = [i for i in issues if i.severity == "WARNING"]
    assert any("Disconnected End Device" in w.title for w in warnings)
