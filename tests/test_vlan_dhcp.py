"""Test suite for VLAN detection, MultiLayerSwitch SVI handling, and DHCP cleanup on PCs."""

from pathlib import Path
import xml.etree.ElementTree as ET
import pktlib

from pkt_planner.parser import parse_pkt_file
from pkt_planner.subnet_detector import detect_subnets
from pkt_planner.vlsm import plan_vlsm_subnets
from pkt_planner.assigner import apply_plan_to_network


def test_vlan_detection_and_dhcp_cleanup(tmp_path):
    vlan_pkt = Path("web/uploads/81ec95c4-d519-46f4-9cbb-1b0e3a38ff95/VLAN_3_Storey_Building.pkt")
    if not vlan_pkt.exists():
        return

    net, topo = parse_pkt_file(vlan_pkt)
    subnets, issues = detect_subnets(topo)

    # Must detect 4 subnets: VLAN 10, 20, 30, and 99
    assert len(subnets) == 4
    vlan_names = [s.name for s in subnets]
    assert any("VLAN 10" in name for name in vlan_names)
    assert any("VLAN 20" in name for name in vlan_names)
    assert any("VLAN 30" in name for name in vlan_names)
    assert any("VLAN 99" in name for name in vlan_names)

    # VLSM plan
    plans = plan_vlsm_subnets("192.168.1.0/24", subnets)
    assert len(plans) == 4

    out_pkt = tmp_path / "vlan_configured.pkt"
    ok, msg = apply_plan_to_network(vlan_pkt, out_pkt, plans, add_test_pings=False)
    assert ok is True

    # Reload and verify all PCs have static IP, mask, gateway and no DHCP entry
    net_out = pktlib.load(out_pkt, strict=False)
    pcs = [d for d in net_out.devices if d.kind == "Pc"]
    assert len(pcs) == 12

    for pc in pcs:
        port = pc["FastEthernet0"]
        assert port.ip is not None and port.ip.startswith("192.168.1.")
        assert port.mask is not None and port.mask != ""
        assert pc.gateway is not None and pc.gateway.startswith("192.168.1.")
        
        # Check XML DHCP_CLIENT entry is removed
        dhcp = pc.el.find(".//DHCP_CLIENT/PORT_DATA_MAP")
        if dhcp is not None:
            entries = [e.find("PORT").text for e in dhcp.findall("PORT_DATA_ENTRY") if e.find("PORT") is not None]
            assert "FastEthernet0" not in entries

        # Check UP_METHOD is 5 (static)
        up_m = port.el.find("UP_METHOD")
        assert up_m is not None and up_m.text == "5"

    # Verify MultiLayerSwitch SVIs
    mls = net_out.device("CORE-MLS")
    for v in ["Vlan10", "Vlan20", "Vlan30", "Vlan99"]:
        assert v in mls.interfaces
        assert mls.interfaces[v].address is not None
        assert mls.interfaces[v].address.startswith("192.168.1.")
