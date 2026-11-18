"""Unit tests for topology parsing and subnet boundary detection."""

from pkt_planner.models import DeviceInfo, LinkInfo, NetworkTopology, PortInfo
from pkt_planner.subnet_detector import detect_subnets


def create_mock_topology():
    """Builds an in-memory 2-LANs mock topology."""
    devices = {
        "R1": DeviceInfo(
            name="R1",
            kind="Router",
            model="1841",
            ports={
                "FastEthernet0/0": PortInfo("R1", "FastEthernet0/0", is_connected=True),
                "FastEthernet0/1": PortInfo("R1", "FastEthernet0/1", is_connected=False),
            },
        ),
        "SW1": DeviceInfo(
            name="SW1",
            kind="Switch",
            model="2960",
            ports={
                "Fa0/1": PortInfo("SW1", "Fa0/1", is_connected=True),
                "Fa0/2": PortInfo("SW1", "Fa0/2", is_connected=True),
                "Fa0/3": PortInfo("SW1", "Fa0/3", is_connected=True),
            },
        ),
        "PC1": DeviceInfo(
            name="PC1",
            kind="Pc",
            model="PC-PT",
            ports={"Fa0": PortInfo("PC1", "Fa0", is_connected=True)},
        ),
        "PC2": DeviceInfo(
            name="PC2",
            kind="Pc",
            model="PC-PT",
            ports={"Fa0": PortInfo("PC2", "Fa0", is_connected=True)},
        ),
    }

    links = [
        LinkInfo("l1", "PC1", "Fa0", "SW1", "Fa0/1"),
        LinkInfo("l2", "PC2", "Fa0", "SW1", "Fa0/2"),
        LinkInfo("l3", "SW1", "Fa0/3", "R1", "FastEthernet0/0"),
    ]

    return NetworkTopology(
        filename="mock.pkt",
        pt_version="8.2.0",
        devices=devices,
        links=links,
        subnets=[],
        issues=[],
    )


def test_detect_subnets_single_lan():
    topology = create_mock_topology()
    subnets, issues = detect_subnets(topology)

    assert len(subnets) == 1
    sub = subnets[0]
    assert sub.gateway is not None
    assert sub.gateway.device == "R1"
    assert sub.gateway.port == "FastEthernet0/0"
    assert sub.status == "detected"
    assert sub.host_count == 3  # R1 + PC1 + PC2


def test_detect_isolated_subnet_without_gateway():
    # PC1 and PC2 connected to Switch SW1 with NO router
    devices = {
        "SW1": DeviceInfo(
            name="SW1",
            kind="Switch",
            model="2960",
            ports={
                "Fa0/1": PortInfo("SW1", "Fa0/1", is_connected=True),
                "Fa0/2": PortInfo("SW1", "Fa0/2", is_connected=True),
            },
        ),
        "PC1": DeviceInfo(
            name="PC1",
            kind="Pc",
            model="PC-PT",
            ports={"Fa0": PortInfo("PC1", "Fa0", is_connected=True)},
        ),
        "PC2": DeviceInfo(
            name="PC2",
            kind="Pc",
            model="PC-PT",
            ports={"Fa0": PortInfo("PC2", "Fa0", is_connected=True)},
        ),
    }
    links = [
        LinkInfo("l1", "PC1", "Fa0", "SW1", "Fa0/1"),
        LinkInfo("l2", "PC2", "Fa0", "SW1", "Fa0/2"),
    ]
    topology = NetworkTopology(
        filename="isolated.pkt",
        pt_version="8.2.0",
        devices=devices,
        links=links,
        subnets=[],
        issues=[],
    )

    subnets, issues = detect_subnets(topology)
    assert len(subnets) == 1
    assert subnets[0].status == "isolated"
    assert subnets[0].gateway is None
    # Issue raised
    assert any(i.severity == "WARNING" and "Isolated Subnet" in i.title for i in issues)


def test_detect_point_to_point_wan():
    # Router R1 directly connected to Router R2
    devices = {
        "R1": DeviceInfo(
            name="R1",
            kind="Router",
            model="1841",
            ports={"Serial0/0/0": PortInfo("R1", "Serial0/0/0", is_connected=True)},
        ),
        "R2": DeviceInfo(
            name="R2",
            kind="Router",
            model="1841",
            ports={"Serial0/0/0": PortInfo("R2", "Serial0/0/0", is_connected=True)},
        ),
    }
    links = [LinkInfo("l1", "R1", "Serial0/0/0", "R2", "Serial0/0/0", "Serial")]
    topology = NetworkTopology(
        filename="wan.pkt",
        pt_version="8.2.0",
        devices=devices,
        links=links,
        subnets=[],
        issues=[],
    )

    subnets, issues = detect_subnets(topology)
    assert len(subnets) == 1
    assert "WAN Link" in subnets[0].name
    assert subnets[0].host_count == 2
