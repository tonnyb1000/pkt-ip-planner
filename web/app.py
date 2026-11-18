"""Flask Web Application for Cisco Packet Tracer IP Planner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pkt_planner import (
    apply_plan_to_network,
    compute_static_routes,
    create_two_lans_sample,
    detect_subnets,
    generate_address_table_csv,
    generate_address_table_markdown,
    generate_cisco_ios_script,
    generate_manual_guide,
    parse_pkt_file,
    plan_vlsm_subnets,
    run_full_validation,
    SubnetBoundary,
    SubnetMember,
    PortRef,
)

app = Flask(__name__)
app.secret_key = "packet-tracer-ip-planner-secret-key"

UPLOAD_DIR = PROJECT_ROOT / "web" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# In-memory session cache for active sessions (key: session_id)
SESSION_DATA: Dict[str, Dict[str, Any]] = {}


def get_pt_binary() -> str | None:
    """Finds Packet Tracer executable on Windows."""
    candidates = [
        r"C:\Program Files\Cisco Packet Tracer 8.2.2\bin\PacketTracer.exe",
        r"C:\Program Files\Cisco Packet Tracer 8.2.1\bin\PacketTracer.exe",
        r"C:\Program Files\Cisco Packet Tracer 8.2.0\bin\PacketTracer.exe",
        r"C:\Program Files\Cisco Packet Tracer 8.1.1\bin\PacketTracer.exe",
        r"C:\Program Files\Cisco Packet Tracer 8.0\bin\PacketTracer.exe",
        r"C:\Program Files (x86)\Cisco Packet Tracer 8.2.2\bin\PacketTracer.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    # Try finding in PATH
    which = shutil.which("PacketTracer") or shutil.which("PacketTracer.exe")
    return which


@app.route("/")
def index():
    return render_template("index.html", pt_installed=bool(get_pt_binary()))


@app.route("/upload", methods=["POST"])
def upload_file():
    session_id = str(uuid.uuid4())
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    use_sample = request.form.get("use_sample") == "true"
    base_cidr = request.form.get("base_cidr", "192.168.1.0/24").strip() or "192.168.1.0/24"

    if use_sample:
        input_pkt = session_dir / "two_lans_sample.pkt"
        create_two_lans_sample(input_pkt)
    else:
        file = request.files.get("pkt_file")
        if not file or not file.filename:
            flash("Please select a .pkt file or load the sample network.", "danger")
            return redirect(url_for("index"))
        if not file.filename.lower().endswith((".pkt", ".pka")):
            flash("File must have a .pkt extension.", "warning")
            return redirect(url_for("index"))
        input_pkt = session_dir / file.filename
        file.save(input_pkt)

    try:
        net, topology = parse_pkt_file(input_pkt)
        subnets, detect_issues = detect_subnets(topology)
    except Exception as e:
        flash(f"Error parsing Packet Tracer file: {e}", "danger")
        return redirect(url_for("index"))

    # Prepare topology graph data for frontend rendering
    devices_json = []
    for d_name, d_info in topology.devices.items():
        devices_json.append({
            "name": d_name,
            "kind": d_info.kind,
            "model": d_info.model,
            "x": d_info.x,
            "y": d_info.y,
            "is_supported": d_info.is_supported,
            "ports": [p.name for p in d_info.ports.values() if p.is_connected],
        })

    links_json = []
    for l in topology.links:
        links_json.append({
            "id": l.id,
            "source": l.device_a,
            "sourcePort": l.port_a,
            "target": l.device_b,
            "targetPort": l.port_b,
            "cable": l.cable_type,
        })

    SESSION_DATA[session_id] = {
        "input_pkt": str(input_pkt),
        "filename": input_pkt.name,
        "base_cidr": base_cidr,
        "topology": topology,
        "subnets": subnets,
        "devices_json": devices_json,
        "links_json": links_json,
    }

    return redirect(url_for("review_subnets", session_id=session_id))


@app.route("/review/<session_id>")
def review_subnets(session_id: str):
    sess = SESSION_DATA.get(session_id)
    if not sess:
        flash("Session expired or invalid. Please start again.", "warning")
        return redirect(url_for("index"))

    return render_template(
        "review.html",
        session_id=session_id,
        filename=sess["filename"],
        base_cidr=sess["base_cidr"],
        topology=sess["topology"],
        subnets=sess["subnets"],
        devices_json=json.dumps(sess["devices_json"]),
        links_json=json.dumps(sess["links_json"]),
    )


@app.route("/plan/<session_id>", methods=["POST"])
def generate_plan(session_id: str):
    sess = SESSION_DATA.get(session_id)
    if not sess:
        flash("Session expired or invalid.", "warning")
        return redirect(url_for("index"))

    base_cidr = request.form.get("base_cidr", sess["base_cidr"]).strip() or sess["base_cidr"]
    sess["base_cidr"] = base_cidr

    subnets: list[SubnetBoundary] = sess["subnets"]

    # Read user confirmed modifications
    for idx, sub in enumerate(subnets):
        name_key = f"subnet_name_{idx}"
        padding_key = f"subnet_padding_{idx}"
        if name_key in request.form and request.form[name_key].strip():
            sub.name = request.form[name_key].strip()
        if padding_key in request.form:
            try:
                sub.padding = max(0, int(request.form[padding_key]))
            except ValueError:
                pass

    try:
        # Run VLSM planning
        plans = plan_vlsm_subnets(base_cidr, subnets)
    except Exception as e:
        flash(f"VLSM Calculation Error: {e}", "danger")
        return redirect(url_for("review_subnets", session_id=session_id))

    # Static routes
    static_routes = compute_static_routes(plans)

    # Validation
    topology = sess["topology"]
    issues = run_full_validation(topology, base_cidr, subnets, plans)

    # Apply to new .pkt file
    input_pkt = Path(sess["input_pkt"])
    output_pkt = input_pkt.parent / f"{input_pkt.stem}_configured.pkt"

    success, assign_msg = apply_plan_to_network(
        source_pkt_path=input_pkt,
        output_pkt_path=output_pkt,
        plans=plans,
        static_routes=static_routes,
        add_test_pings=True,
    )

    # Generate fallback artifacts
    ios_script = generate_cisco_ios_script(plans, static_routes)
    ios_file = input_pkt.parent / f"{input_pkt.stem}_router_config.ios"
    ios_file.write_text(ios_script, encoding="utf-8")

    csv_data = generate_address_table_csv(plans)
    csv_file = input_pkt.parent / f"{input_pkt.stem}_address_table.csv"
    csv_file.write_text(csv_data, encoding="utf-8")

    sess["plans"] = plans
    sess["static_routes"] = static_routes
    sess["issues"] = issues
    sess["output_pkt"] = str(output_pkt)
    sess["output_filename"] = output_pkt.name
    sess["ios_file"] = str(ios_file)
    sess["csv_file"] = str(csv_file)
    sess["assign_success"] = success
    sess["assign_msg"] = assign_msg

    return redirect(url_for("results", session_id=session_id))


@app.route("/results/<session_id>")
def results(session_id: str):
    sess = SESSION_DATA.get(session_id)
    if not sess or "plans" not in sess:
        flash("No active plan found. Please upload a file first.", "warning")
        return redirect(url_for("index"))

    return render_template(
        "results.html",
        session_id=session_id,
        filename=sess["filename"],
        output_filename=sess["output_filename"],
        base_cidr=sess["base_cidr"],
        plans=sess["plans"],
        static_routes=sess["static_routes"],
        issues=sess["issues"],
        assign_success=sess["assign_success"],
        assign_msg=sess["assign_msg"],
        pt_installed=bool(get_pt_binary()),
    )


@app.route("/download/<file_type>/<session_id>")
def download_file(file_type: str, session_id: str):
    sess = SESSION_DATA.get(session_id)
    if not sess:
        return "Session expired", 404

    if file_type == "pkt":
        file_path = sess.get("output_pkt")
        mimetype = "application/octet-stream"
    elif file_type == "ios":
        file_path = sess.get("ios_file")
        mimetype = "text/plain"
    elif file_type == "csv":
        file_path = sess.get("csv_file")
        mimetype = "text/csv"
    else:
        return "Invalid file type", 400

    if not file_path or not Path(file_path).exists():
        return "File not found", 404

    return send_file(file_path, as_attachment=True, mimetype=mimetype)


@app.route("/api/open-pt/<session_id>", methods=["POST"])
def open_packet_tracer(session_id: str):
    sess = SESSION_DATA.get(session_id)
    if not sess or "output_pkt" not in sess:
        return jsonify({"success": False, "error": "Plan not found"}), 404

    output_pkt = Path(sess["output_pkt"])
    if not output_pkt.exists():
        return jsonify({"success": False, "error": "Output file does not exist"}), 404

    pt_bin = get_pt_binary()
    if not pt_bin:
        return jsonify({
            "success": False,
            "error": "Cisco Packet Tracer executable not found on this system.",
        }), 400

    try:
        subprocess.Popen([pt_bin, str(output_pkt.resolve())])
        return jsonify({
            "success": True,
            "message": f"Launched Cisco Packet Tracer with {output_pkt.name}!",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
