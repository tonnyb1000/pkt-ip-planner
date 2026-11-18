"""Data models for Packet Tracer network topology, subnetting, and IP address planning."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PortRef:
    """Reference to a specific port on a device."""
    device: str
    port: str

    def __str__(self) -> str:
        return f"{self.device}.{self.port}"


@dataclass
class PortInfo:
    """Information about a physical or logical port on a device."""
    device_name: str
    name: str
    port_type: str = "Ethernet"  # Ethernet, FastEthernet, GigabitEthernet, Serial, etc.
    is_connected: bool = False
    peer_device: Optional[str] = None
    peer_port: Optional[str] = None
    current_ip: Optional[str] = None
    current_mask: Optional[str] = None
    current_gw: Optional[str] = None
    up: bool = True
    access_vlan: Optional[int] = None
    port_mode: Optional[str] = None

    @property
    def is_serial(self) -> bool:
        lower = self.name.lower()
        return "serial" in lower or lower.startswith("se") or lower.startswith("s")

    @property
    def is_bluetooth(self) -> bool:
        return "bluetooth" in self.name.lower() or self.port_type.lower() == "ebluetooth"


@dataclass
class DeviceInfo:
    """Information about a network device."""
    name: str
    kind: str  # Router, Switch, Pc, Laptop, Server, Printer, etc.
    model: str
    ports: Dict[str, PortInfo] = field(default_factory=dict)
    x: float = 0.0
    y: float = 0.0
    svis: Dict[str, str] = field(default_factory=dict)
    is_supported: bool = True
    support_note: Optional[str] = None

    @property
    def is_router(self) -> bool:
        return self.kind == "Router"

    @property
    def is_multilayer_switch(self) -> bool:
        return self.kind == "MultiLayerSwitch"

    @property
    def is_l3_gateway(self) -> bool:
        return self.is_router or self.is_multilayer_switch

    @property
    def is_switch(self) -> bool:
        return self.kind in {"Switch", "Repeater", "Hub", "Bridge", "MultiLayerSwitch"}

    @property
    def is_end_device(self) -> bool:
        return self.kind in {"Pc", "Laptop", "Server", "Printer"}

    @property
    def is_l3_configurable(self) -> bool:
        """True if IP addresses can be configured on this device."""
        return self.is_router or self.is_multilayer_switch or self.is_end_device


@dataclass
class LinkInfo:
    """A physical cable connecting two device ports."""
    id: str
    device_a: str
    port_a: str
    device_b: str
    port_b: str
    cable_type: str = "StraightThrough"


@dataclass
class SubnetMember:
    """A member port/device in a proposed or detected subnet."""
    device_name: str
    port_name: str
    device_kind: str
    role: str = "host"  # "gateway", "host", "transit"


@dataclass
class SubnetBoundary:
    """A detected or user-adjusted broadcast domain / subnet boundary."""
    subnet_id: str
    name: str
    vlan_id: Optional[int] = None
    gateway: Optional[PortRef] = None
    members: List[SubnetMember] = field(default_factory=list)
    host_count: int = 0
    padding: int = 0  # extra spare IPs requested
    status: str = "detected"  # detected, confirmed, custom, isolated, multi_gateway
    notes: str = ""

    @property
    def total_needed_hosts(self) -> int:
        """Calculates total usable host addresses needed (gateways + hosts + padding)."""
        # Count host members + gateways
        return self.host_count + self.padding


@dataclass
class HostAssignment:
    """The concrete IP address assignment for a device port."""
    device_name: str
    port_name: str
    device_kind: str
    ip: str
    netmask: str
    cidr: str
    gateway: str
    role: str = "host"  # gateway, host, transit

    @property
    def ip_with_prefix(self) -> str:
        prefix = ipaddress.IPv4Network(f"0.0.0.0/{self.netmask}").prefixlen
        return f"{self.ip}/{prefix}"


@dataclass
class SubnetPlan:
    """The calculated VLSM subnet plan for a boundary."""
    subnet_id: str
    name: str
    network: ipaddress.IPv4Network
    prefix: int
    netmask: str
    broadcast: str
    gateway_ip: str
    usable_range: Tuple[str, str]
    needed_hosts: int
    allocated_hosts: int
    assignments: List[HostAssignment] = field(default_factory=list)


@dataclass
class StaticRoute:
    """A static route entry to configure on a router."""
    router_name: str
    destination_network: str  # e.g. 192.168.2.0
    destination_mask: str     # e.g. 255.255.255.0
    next_hop_ip: str          # e.g. 10.0.0.2
    description: str = ""

    @property
    def ios_command(self) -> str:
        return f"ip route {self.destination_network} {self.destination_mask} {self.next_hop_ip}"


@dataclass
class ValidationIssue:
    """A validation problem, warning, or recommendation."""
    severity: str  # ERROR, WARNING, INFO
    title: str
    message: str
    affected_devices: List[str] = field(default_factory=list)


@dataclass
class NetworkTopology:
    """Parsed network topology containing all components."""
    filename: str
    pt_version: str
    devices: Dict[str, DeviceInfo] = field(default_factory=dict)
    links: List[LinkInfo] = field(default_factory=list)
    subnets: List[SubnetBoundary] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)
