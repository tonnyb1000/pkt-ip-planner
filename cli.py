"""Command-line interface (CLI) for Cisco Packet Tracer Automatic IP Planner."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

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
)


def print_banner():
    banner = """
========================================================================
   Cisco Packet Tracer Automatic IP Planner & VLSM Subnet Generator
========================================================================
"""
    print(banner)


def run_cli():
    parser = argparse.ArgumentParser(
        description="Automatically plan and assign IP addresses to Cisco Packet Tracer networks."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to the input .pkt file (or use --sample to generate a starter example).",
    )
    parser.add_argument(
        "base_cidr",
        nargs="?",
        default="192.168.1.0/24",
        help="Starting IPv4 network block (e.g. 192.168.1.0/24, 10.0.0.0/16). Default: 192.168.1.0/24",
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to save the configured .pkt file. Default: <input_name>_configured.pkt",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Generate and use the 2-LANs starter example topology (R1 + SW1/SW2 + 4 PCs).",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Automatically proceed without prompting for subnet confirmation.",
    )
    parser.add_argument(
        "--export-ios",
        help="Export Cisco IOS CLI configuration commands to a .ios / .txt file.",
    )
    parser.add_argument(
        "--export-csv",
        help="Export the IP address assignment table to a CSV file.",
    )
    parser.add_argument(
        "--open-pt",
        action="store_true",
        help="Automatically launch Cisco Packet Tracer with the generated file.",
    )

    args = parser.parse_args()
    print_banner()

    input_path = None
    if args.sample:
        samples_dir = Path(__file__).resolve().parent / "samples"
        samples_dir.mkdir(parents=True, exist_ok=True)
        sample_unconf = samples_dir / "two_lans_starter.pkt"
        create_two_lans_sample(sample_unconf)
        input_path = sample_unconf
        print(f"[*] Generated starter 2-LANs topology at: {input_path}")
    elif args.input_file:
        input_path = Path(args.input_file)
    else:
        # Prompt user
        print("No input file provided. Choose an option:")
        print("  1. Use built-in 2-LANs starter example")
        print("  2. Specify path to your .pkt file")
        choice = input("Enter choice [1/2] (default 1): ").strip()
        if choice == "2":
            entered = input("Enter path to .pkt file: ").strip()
            input_path = Path(entered)
        else:
            samples_dir = Path(__file__).resolve().parent / "samples"
            samples_dir.mkdir(parents=True, exist_ok=True)
            sample_unconf = samples_dir / "two_lans_starter.pkt"
            create_two_lans_sample(sample_unconf)
            input_path = sample_unconf
            print(f"[*] Generated starter 2-LANs topology at: {input_path}")

    if not input_path or not input_path.exists():
        print(f"[!] Error: File '{input_path}' does not exist.")
        sys.exit(1)

    base_cidr = args.base_cidr
    if not args.non_interactive and not args.base_cidr:
        entered_cidr = input(f"Enter starting network address [default {base_cidr}]: ").strip()
        if entered_cidr:
            base_cidr = entered_cidr

    print(f"\n[+] Loading Packet Tracer file: {input_path.name}")
    try:
        net, topology = parse_pkt_file(input_path)
    except Exception as e:
        print(f"[!] Error loading file: {e}")
        sys.exit(1)

    print(f"    Packet Tracer Version Stamp: {topology.pt_version}")
    print(f"    Detected Devices: {len(topology.devices)}")
    print(f"    Detected Links: {len(topology.links)}")

    # Display Devices
    print("\n--- Detected Devices ---")
    for d_name, d_info in topology.devices.items():
        role_desc = d_info.kind
        conn_ports = [p.name for p in d_info.ports.values() if p.is_connected]
        status_flag = " (GUI Only/Limited)" if not d_info.is_supported else ""
        print(f"  * {d_name:<10} [{role_desc}]{status_flag} - Connected ports: {', '.join(conn_ports) or 'None'}")

    # Detect Subnets
    subnets, detect_issues = detect_subnets(topology)
    print(f"\n--- Proposed Subnets (Broadcast Domains) ---")
    for idx, sub in enumerate(subnets, 1):
        gw_str = f"{sub.gateway.device}.{sub.gateway.port}" if sub.gateway else "None (Isolated)"
        member_names = [f"{m.device_name}({m.port_name})" for m in sub.members]
        print(f"\n  [{idx}] {sub.name}")
        print(f"      Gateway: {gw_str}")
        print(f"      Status:  {sub.status.upper()}")
        print(f"      Members: {', '.join(member_names)}")
        print(f"      Notes:   {sub.notes}")

    # Subnet Confirmation
    if not args.non_interactive:
        print("\nDo you want to confirm these proposed subnet boundaries? [Y/n]")
        ans = input("Choice: ").strip().lower()
        if ans == "n":
            print("[*] Entering interactive boundary adjustment:")
            for sub in subnets:
                new_name = input(f"  Name for '{sub.name}' [Enter to keep]: ").strip()
                if new_name:
                    sub.name = new_name
                padding_str = input(f"  Extra spare IP addresses to reserve for {sub.name} [default {sub.padding}]: ").strip()
                if padding_str.isdigit():
                    sub.padding = int(padding_str)

    # VLSM Planning
    print(f"\n[+] Calculating VLSM non-overlapping subnets from base: {base_cidr} ...")
    try:
        plans = plan_vlsm_subnets(base_cidr, subnets)
    except Exception as e:
        print(f"[!] Subnet planning error: {e}")
        sys.exit(1)

    # Static Routes for multi-router networks
    static_routes = compute_static_routes(plans)

    # Run Full Validation
    validation_issues = run_full_validation(topology, base_cidr, subnets, plans)
    if validation_issues:
        print("\n--- Validation Warnings & Recommendations ---")
        for issue in validation_issues:
            print(f"  [{issue.severity}] {issue.title}: {issue.message}")

    # Display Address Table
    print("\n" + "=" * 80)
    print("                      IP ADDRESS ALLOCATION TABLE")
    print("=" * 80)
    md_table = generate_address_table_markdown(plans)
    print(md_table)
    print("=" * 80)

    # Determine Output File
    output_path = args.output
    if not output_path:
        output_path = input_path.parent / f"{input_path.stem}_configured.pkt"
    else:
        output_path = Path(output_path)

    print(f"\n[+] Applying configuration and writing new file: {output_path.name} ...")
    success, msg = apply_plan_to_network(
        source_pkt_path=input_path,
        output_pkt_path=output_path,
        plans=plans,
        static_routes=static_routes,
        add_test_pings=True,
    )

    if success:
        print(f"[OK] SUCCESS: {msg}")
    else:
        print(f"[!] WARNING: Could not directly write to .pkt file: {msg}")
        print("[!] Generating manual fallback scripts instead.")

    # Optional Exports
    if args.export_ios:
        ios_path = Path(args.export_ios)
        ios_script = generate_cisco_ios_script(plans, static_routes)
        ios_path.write_text(ios_script, encoding="utf-8")
        print(f"[+] Exported Cisco IOS commands to: {ios_path}")

    if args.export_csv:
        csv_path = Path(args.export_csv)
        csv_data = generate_address_table_csv(plans)
        csv_path.write_text(csv_data, encoding="utf-8")
        print(f"[+] Exported CSV Address Table to: {csv_path}")

    # Open in Packet Tracer if requested
    if args.open_pt and output_path.exists():
        pt_binary = r"C:\Program Files\Cisco Packet Tracer 8.2.2\bin\PacketTracer.exe"
        if Path(pt_binary).exists():
            print(f"\n[+] Launching Cisco Packet Tracer with {output_path.name} ...")
            try:
                subprocess.Popen([pt_binary, str(output_path.resolve())])
                print("[OK] Cisco Packet Tracer launched! Test connectivity using Ping or the PDU list.")
            except Exception as e:
                print(f"[!] Could not launch Packet Tracer: {e}")
        else:
            print(f"[!] Packet Tracer binary not found at standard path: {pt_binary}")

    print("\nDone! All operations completed successfully.")


if __name__ == "__main__":
    run_cli()
