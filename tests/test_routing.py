"""Unit tests for multi-router static routing calculation."""

import ipaddress
from pkt_planner.models import HostAssignment, SubnetPlan
from pkt_planner.routing import compute_static_routes


def test_single_router_no_static_routes():
    # R1 connected to LAN1 and LAN2: connected routes are sufficient!
    p1 = SubnetPlan(
        subnet_id="sub_1",
        name="LAN 1",
        network=ipaddress.IPv4Network("192.168.1.0/25"),
        prefix=25,
        netmask="255.255.255.128",
        broadcast="192.168.1.127",
        gateway_ip="192.168.1.1",
        usable_range=("192.168.1.1", "192.168.1.126"),
        needed_hosts=2,
        allocated_hosts=126,
        assignments=[
            HostAssignment("R1", "Fa0/0", "Router", "192.168.1.1", "255.255.255.128", "192.168.1.1/25", "192.168.1.1", "gateway"),
        ],
    )
    p2 = SubnetPlan(
        subnet_id="sub_2",
        name="LAN 2",
        network=ipaddress.IPv4Network("192.168.1.128/25"),
        prefix=25,
        netmask="255.255.255.128",
        broadcast="192.168.1.255",
        gateway_ip="192.168.1.129",
        usable_range=("192.168.1.129", "192.168.1.254"),
        needed_hosts=2,
        allocated_hosts=126,
        assignments=[
            HostAssignment("R1", "Fa0/1", "Router", "192.168.1.129", "255.255.255.128", "192.168.1.129/25", "192.168.1.129", "gateway"),
        ],
    )

    routes = compute_static_routes([p1, p2])
    assert routes == {"R1": []}


def test_two_routers_static_routes():
    # R1 is connected to LAN1 (192.168.1.0/24) and WAN1 (10.0.0.0/30)
    # R2 is connected to LAN2 (192.168.2.0/24) and WAN1 (10.0.0.0/30)
    # R1's WAN IP: 10.0.0.1, R2's WAN IP: 10.0.0.2
    lan1 = SubnetPlan(
        subnet_id="lan_1",
        name="LAN 1",
        network=ipaddress.IPv4Network("192.168.1.0/24"),
        prefix=24,
        netmask="255.255.255.0",
        broadcast="192.168.1.255",
        gateway_ip="192.168.1.1",
        usable_range=("192.168.1.1", "192.168.1.254"),
        needed_hosts=2,
        allocated_hosts=254,
        assignments=[
            HostAssignment("R1", "Fa0/0", "Router", "192.168.1.1", "255.255.255.0", "192.168.1.1/24", "192.168.1.1", "gateway"),
        ],
    )
    wan1 = SubnetPlan(
        subnet_id="wan_1",
        name="WAN Link",
        network=ipaddress.IPv4Network("10.0.0.0/30"),
        prefix=30,
        netmask="255.255.255.252",
        broadcast="10.0.0.3",
        gateway_ip="10.0.0.1",
        usable_range=("10.0.0.1", "10.0.0.2"),
        needed_hosts=2,
        allocated_hosts=2,
        assignments=[
            HostAssignment("R1", "Se0/0/0", "Router", "10.0.0.1", "255.255.255.252", "10.0.0.1/30", "10.0.0.1", "gateway"),
            HostAssignment("R2", "Se0/0/0", "Router", "10.0.0.2", "255.255.255.252", "10.0.0.2/30", "10.0.0.2", "transit"),
        ],
    )
    lan2 = SubnetPlan(
        subnet_id="lan_2",
        name="LAN 2",
        network=ipaddress.IPv4Network("192.168.2.0/24"),
        prefix=24,
        netmask="255.255.255.0",
        broadcast="192.168.2.255",
        gateway_ip="192.168.2.1",
        usable_range=("192.168.2.1", "192.168.2.254"),
        needed_hosts=2,
        allocated_hosts=254,
        assignments=[
            HostAssignment("R2", "Fa0/0", "Router", "192.168.2.1", "255.255.255.0", "192.168.2.1/24", "192.168.2.1", "gateway"),
        ],
    )

    routes = compute_static_routes([lan1, wan1, lan2])

    assert "R1" in routes
    assert "R2" in routes

    # R1 must have route to LAN2 (192.168.2.0) via 10.0.0.2
    assert len(routes["R1"]) == 1
    r1_route = routes["R1"][0]
    assert r1_route.destination_network == "192.168.2.0"
    assert r1_route.next_hop_ip == "10.0.0.2"
    assert r1_route.ios_command == "ip route 192.168.2.0 255.255.255.0 10.0.0.2"

    # R2 must have route to LAN1 (192.168.1.0) via 10.0.0.1
    assert len(routes["R2"]) == 1
    r2_route = routes["R2"][0]
    assert r2_route.destination_network == "192.168.1.0"
    assert r2_route.next_hop_ip == "10.0.0.1"
    assert r2_route.ios_command == "ip route 192.168.1.0 255.255.255.0 10.0.0.1"
