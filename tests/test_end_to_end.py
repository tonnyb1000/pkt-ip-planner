"""End-to-end integration tests for Packet Tracer IP Planner and Flask Web UI."""

from pathlib import Path
import tempfile
import pktlib

from pkt_planner import (
    apply_plan_to_network,
    compute_static_routes,
    create_two_lans_sample,
    detect_subnets,
    parse_pkt_file,
    plan_vlsm_subnets,
)
from web.app import app


def test_end_to_end_pkt_generation_and_reload(tmp_path: Path):
    # 1. Create starter sample network
    unconf_pkt = tmp_path / "starter.pkt"
    create_two_lans_sample(unconf_pkt)
    orig_bytes = unconf_pkt.read_bytes()

    # 2. Parse file
    net, topology = parse_pkt_file(unconf_pkt)
    assert len(topology.devices) == 7
    assert len(topology.links) == 6

    # 3. Detect subnets
    subnets, issues = detect_subnets(topology)
    assert len(subnets) == 2

    # 4. Plan VLSM
    plans = plan_vlsm_subnets("192.168.1.0/24", subnets)
    assert len(plans) == 2

    # 5. Apply plan to new file
    output_pkt = tmp_path / "configured.pkt"
    static_routes = compute_static_routes(plans)
    success, msg = apply_plan_to_network(
        source_pkt_path=unconf_pkt,
        output_pkt_path=output_pkt,
        plans=plans,
        static_routes=static_routes,
        add_test_pings=True,
    )
    assert success is True
    assert output_pkt.exists()

    # 6. Verify original file untouched
    assert unconf_pkt.read_bytes() == orig_bytes, "Original .pkt file was altered!"

    # 7. Reload and verify configured .pkt
    reloaded_net = pktlib.load(output_pkt, strict=False)

    # Check PC1
    pc1 = reloaded_net.device("PC1")
    assert pc1["fa0"].ip == "192.168.1.2"
    assert pc1["fa0"].mask == "255.255.255.248"
    assert pc1.gateway == "192.168.1.1"

    # Check PC3
    pc3 = reloaded_net.device("PC3")
    assert pc3["fa0"].ip == "192.168.1.10"
    assert pc3["fa0"].mask == "255.255.255.248"
    assert pc3.gateway == "192.168.1.9"

    # Check Router R1
    r1 = reloaded_net.device("R1")
    assert r1["fa0/0"].ip == "192.168.1.1"
    assert r1["fa0/1"].ip == "192.168.1.9"

    # Verify IOS running config on R1 contains IP address commands
    r1_cfg_str = "\n".join(r1.running_config)
    assert "ip address 192.168.1.1 255.255.255.248" in r1_cfg_str
    assert "ip address 192.168.1.9 255.255.255.248" in r1_cfg_str


def test_web_ui_flow():
    client = app.test_client()

    # 1. Landing page
    res = client.get("/")
    assert res.status_code == 200
    assert b"Packet Tracer IP Planner" in res.data

    # 2. Upload sample network
    res = client.post(
        "/upload",
        data={"use_sample": "true", "base_cidr": "192.168.1.0/24"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    review_url = res.headers["Location"]
    session_id = review_url.split("/")[-1]

    # 3. Review page
    res = client.get(f"/review/{session_id}")
    assert res.status_code == 200
    assert b"Topology Discovery &amp; Subnet Confirmation" in res.data or b"Topology Discovery & Subnet Confirmation" in res.data

    # 4. Generate plan
    res = client.post(
        f"/plan/{session_id}",
        data={
            "base_cidr": "192.168.1.0/24",
            "subnet_name_0": "LAN Alpha",
            "subnet_padding_0": "2",
            "subnet_name_1": "LAN Beta",
            "subnet_padding_1": "2",
        },
        follow_redirects=False,
    )
    assert res.status_code == 302
    results_url = res.headers["Location"]

    # 5. Results page
    res = client.get(f"/results/{session_id}")
    assert res.status_code == 200
    assert b"IP Addresses Successfully Assigned" in res.data
    assert b"LAN Alpha" in res.data
    assert b"LAN Beta" in res.data

    # 6. Test downloads
    pkt_res = client.get(f"/download/pkt/{session_id}")
    assert pkt_res.status_code == 200
    assert len(pkt_res.data) > 0

    ios_res = client.get(f"/download/ios/{session_id}")
    assert ios_res.status_code == 200
    assert b"interface FastEthernet0/0" in ios_res.data

    csv_res = client.get(f"/download/csv/{session_id}")
    assert csv_res.status_code == 200
    assert b"Device Name,Device Type" in csv_res.data
