"""Packet Tracer IP Planner package."""

from .assigner import apply_plan_to_network
from .fallback import (
    generate_address_table_csv,
    generate_address_table_markdown,
    generate_cisco_ios_script,
    generate_manual_guide,
)
from .models import (
    DeviceInfo,
    HostAssignment,
    LinkInfo,
    NetworkTopology,
    PortInfo,
    PortRef,
    StaticRoute,
    SubnetBoundary,
    SubnetMember,
    SubnetPlan,
    ValidationIssue,
)
from .parser import parse_pkt_file
from .routing import compute_static_routes
from .sample_generator import create_two_lans_sample
from .subnet_detector import detect_subnets
from .validator import (
    run_full_validation,
    validate_address_space,
    validate_duplicate_addresses,
    validate_network_structure,
)
from .vlsm import InsufficientAddressSpaceError, get_prefix_for_hosts, plan_vlsm_subnets

__all__ = [
    "parse_pkt_file",
    "detect_subnets",
    "plan_vlsm_subnets",
    "apply_plan_to_network",
    "compute_static_routes",
    "create_two_lans_sample",
    "run_full_validation",
    "validate_address_space",
    "validate_duplicate_addresses",
    "validate_network_structure",
    "generate_cisco_ios_script",
    "generate_address_table_markdown",
    "generate_address_table_csv",
    "generate_manual_guide",
    "InsufficientAddressSpaceError",
    "get_prefix_for_hosts",
    "NetworkTopology",
    "DeviceInfo",
    "PortInfo",
    "PortRef",
    "LinkInfo",
    "SubnetBoundary",
    "SubnetMember",
    "SubnetPlan",
    "HostAssignment",
    "StaticRoute",
    "ValidationIssue",
]
