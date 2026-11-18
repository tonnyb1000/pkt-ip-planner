"""Generator script to produce a professional 10-slide PowerPoint presentation (.pptx)
for the Cisco Packet Tracer Automatic IP Planner project.
"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE


def build_presentation(output_path: Path):
    prs = Presentation()
    # 16:9 Widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]

    # Color Palette
    COLOR_BG = RGBColor(248, 250, 252)        # Light Slate (#f8fafc)
    COLOR_PRIMARY = RGBColor(15, 23, 42)      # Deep Navy (#0f172a)
    COLOR_ACCENT = RGBColor(37, 99, 235)      # Blue (#2563eb)
    COLOR_ACCENT_LIGHT = RGBColor(239, 246, 255) # Light Blue (#eff6ff)
    COLOR_TEXT = RGBColor(51, 65, 85)         # Slate Gray (#334155)
    COLOR_MUTED = RGBColor(100, 116, 139)     # Muted Slate (#64748b)
    COLOR_WHITE = RGBColor(255, 255, 255)
    COLOR_CARD_BORDER = RGBColor(226, 232, 240)

    slides_data = [
        # Slide 1: Title
        {
            "is_title": True,
            "badge": "NETWORK AUTOMATION FOR EDUCATION",
            "title": "Automating IP Addressing for Cisco Packet Tracer",
            "subtitle": "From a blank topology to a fully configured, ping-ready network in 5 seconds",
            "meta": "A Human-Centered Project Walkthrough | CCNA & Network Engineering",
            "notes": (
                "If you've ever studied for the CCNA or taught a networking class, you know the drill: "
                "you draw out a great network in Packet Tracer, and then your momentum completely halts. "
                "You have to open dialog box after dialog box to type in IP addresses, subnet masks, and "
                "default gateways by hand. Today, we're showing how we turned that entire 30-minute chore "
                "into a single-click automated process."
            )
        },
        # Slide 2: The Problem
        {
            "badge": "THE PROBLEM",
            "title": "The Manual Subnetting Grind",
            "subtitle": "Where network lab momentum and student focus break down",
            "cards": [
                {
                    "title": "Calculations on Scratch Paper",
                    "text": "Working out VLSM block sizes, network IDs, and broadcast boundaries by hand before even opening the software."
                },
                {
                    "title": "Endless Repetitive Clicking",
                    "text": "Opening every single PC > Desktop > IP Configuration > typing 3 separate fields (IP, mask, gateway) across dozens of machines."
                },
                {
                    "title": "The Inevitable Typo",
                    "text": "A single mistyped digit on a default gateway silently breaks routing, leaving students debugging typos rather than learning protocols."
                }
            ],
            "notes": (
                "The problem isn't drawing the topology—Packet Tracer is great for that. The problem is the tedious "
                "data entry. In a 20-device lab, you're typing over 60 IP fields. If you make just one typo on a default "
                "gateway, your ping fails, and you spend half the class tracking down a mistyped digit instead of studying "
                "how routers work."
            )
        },
        # Slide 3: Why Existing Tools Fall Short
        {
            "badge": "THE GAP",
            "title": "Calculators Give You Numbers, Not Networks",
            "subtitle": "Why web calculators and spreadsheets don't solve the core bottleneck",
            "cards": [
                {
                    "title": "Isolated Math",
                    "text": "Online subnet calculators output a flat list of subnets. They have zero awareness of your actual cables, switches, or router ports."
                },
                {
                    "title": "Manual Mapping Required",
                    "text": "You still have to manually map which subnet belongs to which interface, then manually type every number into Packet Tracer."
                },
                {
                    "title": "The Dream Workflow",
                    "text": "What if an application could directly read your .pkt file, trace the cables, deduce the subnets, and write the IP configuration straight into the file?"
                }
            ],
            "notes": (
                "You might ask: aren't there subnet calculators online? Yes, but they only do math in isolation. "
                "They don't know that PC1 is plugged into Port Fa0/1 on Switch 1, or which router port is the gateway. "
                "You still have to do all the typing yourself. We wanted something that actually interacts with the lab file itself."
            )
        },
        # Slide 4: Cracking the .pkt File
        {
            "badge": "THE ENGINEERING CHALLENGE",
            "title": "Packet Tracer Files Aren't Plain Text",
            "subtitle": "Reverse-engineering the proprietary .pkt container format",
            "cards": [
                {
                    "title": "4-Layer Container",
                    "text": "A .pkt file is an encrypted container: outer byte-reversal XOR, Twofish-EAX authenticated cipher, inner XOR scrambler, and Qt qCompress (zlib)."
                },
                {
                    "title": "Strict Version Checks",
                    "text": "Packet Tracer checks version stamps on open. Our research verified that using strict=False in pktlib lets us handle modern versions (e.g. 8.2.2)."
                },
                {
                    "title": "Preserving Layouts",
                    "text": "The decoder mutates the underlying XML directly, ensuring visual positions, custom cables, modules, and notes remain 100% untouched."
                }
            ],
            "notes": (
                "This wasn't as simple as opening a zip file. Cisco Packet Tracer encrypts its save files with "
                "Twofish-EAX encryption and compresses them with Qt's zlib engine. Through our research and "
                "testing with the pktlib library, we proved we can open the container, modify device IP properties, "
                "and seal it back up cleanly—without shifting your devices or breaking existing cables."
            )
        },
        # Slide 5: The End-to-End Solution
        {
            "badge": "THE SOLUTION",
            "title": "An Intelligent End-to-End Workflow",
            "subtitle": "A clean 4-step process designed for beginners and power users alike",
            "cards": [
                {
                    "title": "1. Build & Save",
                    "text": "Build and connect your devices in Packet Tracer, then save the workspace as a standard .pkt file."
                },
                {
                    "title": "2. Upload & Base CIDR",
                    "text": "Upload the file to our visual web app and choose a starting network block (e.g. 192.168.1.0/24)."
                },
                {
                    "title": "3. Review & Confirm",
                    "text": "Inspect the interactive topology map. Review detected subnets and adjust spare host capacity."
                },
                {
                    "title": "4. Download & Ping",
                    "text": "Download the newly configured .pkt file, open it in Packet Tracer, and test connectivity immediately!"
                }
            ],
            "notes": (
                "Here is how simple we made it for a beginner. You draw your network in Packet Tracer just like "
                "you normally do. You save it, drop it into our tool, type in your base network like 192.168.1.0/24, "
                "review the detected subnets, and hit 'Generate'. You get back a configured file ready to open in Packet Tracer."
            )
        },
        # Slide 6: Subnet Discovery
        {
            "badge": "HOW IT WORKS: PART 1",
            "title": "Topology Discovery & Subnet Detection",
            "subtitle": "Using graph theory to find broadcast domains automatically",
            "cards": [
                {
                    "title": "Graph Traversal (BFS)",
                    "text": "The engine explores outward along cables starting from each Layer 3 endpoint (PCs and router interfaces)."
                },
                {
                    "title": "Switches Connect, Routers Divide",
                    "text": "Layer 2 switches and hubs forward frames without routing, grouping attached PCs and router ports into a single broadcast domain."
                },
                {
                    "title": "Automatic Gateways",
                    "text": "The router port in each broadcast domain is automatically designated as that subnet's Default Gateway."
                }
            ],
            "notes": (
                "How does the program know what a subnet is? It uses graph search. Switches and hubs don't separate "
                "broadcast domains; they connect them. Routers, on the other hand, separate them. So the algorithm travels "
                "through the switches until it hits a router port. That router port becomes the default gateway, and all the "
                "PCs attached to those switches become hosts in that subnet."
            )
        },
        # Slide 7: VLSM Planning
        {
            "badge": "HOW IT WORKS: PART 2",
            "title": "Smart VLSM Address Allocation",
            "subtitle": "Optimal sizing without wasting precious IPv4 address space",
            "cards": [
                {
                    "title": "Accurate Sizing",
                    "text": "Calculates required hosts: Needed = Devices + Gateways + User Spare Padding. Sizes masks from /24 down to /30 point-to-point links."
                },
                {
                    "title": "Descending Order Sort",
                    "text": "Allocates largest subnets first—the foundational rule of VLSM that guarantees non-overlapping blocks without address fragmentation."
                },
                {
                    "title": "Structured Assignment",
                    "text": "Default gateway receives the first usable address (.1); end devices receive sequential usable addresses (.2, .3, ...)."
                }
            ],
            "notes": (
                "Once subnets are identified, we apply Variable Length Subnet Masking (VLSM). The biggest mistake "
                "students make with VLSM is address fragmentation. Our engine automatically sorts subnets by size, "
                "placing the largest subnet first, then the next, and so on. A point-to-point router link gets a tight "
                "/30 block, while a busy LAN gets a /28 or /26, maximizing efficiency."
            )
        },
        # Slide 8: Configuration & Routing Automation
        {
            "badge": "HOW IT WORKS: PART 3",
            "title": "Device Configuration & Inter-Subnet Routing",
            "subtitle": "Writing configurations and making remote subnets reachable",
            "cards": [
                {
                    "title": "End Device Setup",
                    "text": "Sets static IP, subnet mask, and default gateway simultaneously, safely avoiding Packet Tracer GUI mismatch errors."
                },
                {
                    "title": "Router Interfaces Up",
                    "text": "Configures router interfaces with IP addresses and automatically injects 'no shutdown' so ports turn green."
                },
                {
                    "title": "Multi-Router Static Routes",
                    "text": "Calculates shortest router hops and writes 'ip route' commands so LANs across different routers can communicate."
                },
                {
                    "title": "Embedded Ping Tests",
                    "text": "Injects ICMP Echo Simple PDUs right into the .pkt file, allowing one-click verification in Packet Tracer's GUI."
                }
            ],
            "notes": (
                "When writing the changes, the engine doesn't just configure PCs. On routers, it configures interface "
                "IPs and runs 'no shutdown' so the ports turn green. Even better: if you have two routers connected together, "
                "it calculates the next-hop static routes so LAN 1 can actually reach LAN 2. It even drops ready-to-fire "
                "ping packets right into the Packet Tracer scenario bar."
            )
        },
        # Slide 9: Safety & Validation
        {
            "badge": "SAFETY & RELIABILITY",
            "title": "Validation Engine & Practical Fallbacks",
            "subtitle": "Defensive design for real-world edge cases and unsupported hardware",
            "cards": [
                {
                    "title": "Pre-Flight Validation",
                    "text": "Catches address space exhaustion, duplicate IPs, disconnected devices, or missing gateways before generating any file."
                },
                {
                    "title": "Non-Destructive Guarantee",
                    "text": "Your original .pkt file is never overwritten. Changes are saved to a new, cleanly named file."
                },
                {
                    "title": "Full Manual Fallback",
                    "text": "If an exotic device cannot be modified offline, the app exports ready-to-paste Cisco IOS scripts (.ios) and CSV address tables."
                }
            ],
            "notes": (
                "We built this defensively. If your base network isn't big enough to fit all your PCs, it stops and "
                "tells you exactly what size block you need. It guarantees no duplicate IPs. And if you have a special "
                "device that Packet Tracer only configures in its GUI, the tool generates a clean, ready-to-paste Cisco IOS "
                "script and a CSV address table so you can apply the plan manually."
            )
        },
        # Slide 10: Summary & Roadmap
        {
            "badge": "LOOKING FORWARD",
            "title": "Summary & Future Roadmap",
            "subtitle": "Freeing students and engineers to focus on real networking concepts",
            "cards": [
                {
                    "title": "What's Working Today",
                    "text": "100% test pass rate across 15 unit and integration tests. Verified in Packet Tracer 8.2.2. Dual Web UI and CLI available."
                },
                {
                    "title": "Impact",
                    "text": "Cuts 30 minutes of error-prone typing down to 5 seconds, transforming network lab workflows for educators and students."
                },
                {
                    "title": "Upcoming Features",
                    "text": "Automatic DHCP pool configuration on routers, 802.1Q VLAN trunking with sub-interfaces, and dynamic routing (OSPF / RIP)."
                }
            ],
            "notes": (
                "To wrap up: this tool transforms network lab setup from a frustrating exercise in typing into a fast, "
                "educational experience. Students can see how VLSM works visually, verify their topologies instantly, "
                "and focus on real network engineering. All 15 automated tests are passing, and it's ready to use today."
            )
        }
    ]

    for data in slides_data:
        slide = prs.slides.add_slide(blank_layout)

        # Set Slide Background
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = COLOR_PRIMARY if data.get("is_title") else COLOR_BG
        bg.line.fill.background()

        # Add Presenter Notes
        notes_slide = slide.notes_slide
        text_frame = notes_slide.notes_text_frame
        text_frame.text = data["notes"]

        if data.get("is_title"):
            # Title Slide Layout
            badge_box = slide.shapes.add_textbox(Inches(1.2), Inches(1.5), Inches(10), Inches(0.5))
            tf_badge = badge_box.text_frame
            p_badge = tf_badge.paragraphs[0]
            p_badge.text = data["badge"]
            p_badge.font.name = "Arial"
            p_badge.font.size = Pt(13)
            p_badge.font.bold = True
            p_badge.font.color.rgb = COLOR_ACCENT

            title_box = slide.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(10.8), Inches(2.2))
            tf_title = title_box.text_frame
            tf_title.word_wrap = True
            p_title = tf_title.paragraphs[0]
            p_title.text = data["title"]
            p_title.font.name = "Arial"
            p_title.font.size = Pt(40)
            p_title.font.bold = True
            p_title.font.color.rgb = COLOR_WHITE

            sub_box = slide.shapes.add_textbox(Inches(1.2), Inches(4.5), Inches(10.8), Inches(1.2))
            tf_sub = sub_box.text_frame
            tf_sub.word_wrap = True
            p_sub = tf_sub.paragraphs[0]
            p_sub.text = data["subtitle"]
            p_sub.font.name = "Arial"
            p_sub.font.size = Pt(20)
            p_sub.font.color.rgb = RGBColor(203, 213, 225) # Slate 300

            meta_box = slide.shapes.add_textbox(Inches(1.2), Inches(6.0), Inches(10), Inches(0.5))
            tf_meta = meta_box.text_frame
            p_meta = tf_meta.paragraphs[0]
            p_meta.text = data["meta"]
            p_meta.font.name = "Arial"
            p_meta.font.size = Pt(13)
            p_meta.font.color.rgb = COLOR_MUTED

        else:
            # Content Slide Header
            badge_box = slide.shapes.add_textbox(Inches(1.0), Inches(0.6), Inches(10), Inches(0.4))
            tf_badge = badge_box.text_frame
            p_badge = tf_badge.paragraphs[0]
            p_badge.text = data["badge"]
            p_badge.font.name = "Arial"
            p_badge.font.size = Pt(11)
            p_badge.font.bold = True
            p_badge.font.color.rgb = COLOR_ACCENT

            title_box = slide.shapes.add_textbox(Inches(1.0), Inches(0.95), Inches(11.3), Inches(0.8))
            tf_title = title_box.text_frame
            p_title = tf_title.paragraphs[0]
            p_title.text = data["title"]
            p_title.font.name = "Arial"
            p_title.font.size = Pt(28)
            p_title.font.bold = True
            p_title.font.color.rgb = COLOR_PRIMARY

            sub_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.75), Inches(11.3), Inches(0.5))
            tf_sub = sub_box.text_frame
            p_sub = tf_sub.paragraphs[0]
            p_sub.text = data["subtitle"]
            p_sub.font.name = "Arial"
            p_sub.font.size = Pt(14)
            p_sub.font.color.rgb = COLOR_MUTED

            # Cards Layout (3 or 4 cards horizontally)
            cards = data.get("cards", [])
            num_cards = len(cards)
            margin_left = 1.0
            total_width = 11.333
            card_gap = 0.35
            card_width = (total_width - (num_cards - 1) * card_gap) / num_cards
            card_top = 2.45
            card_height = 4.2

            for i, card in enumerate(cards):
                left_pos = margin_left + i * (card_width + card_gap)

                # Card background shape
                card_shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(left_pos), Inches(card_top), Inches(card_width), Inches(card_height)
                )
                card_shape.fill.solid()
                card_shape.fill.fore_color.rgb = COLOR_WHITE
                card_shape.line.color.rgb = COLOR_CARD_BORDER
                card_shape.line.width = Pt(1.5)

                # Card top accent bar
                bar = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(left_pos + 0.02), Inches(card_top + 0.02), Inches(card_width - 0.04), Inches(0.12)
                )
                bar.fill.solid()
                bar.fill.fore_color.rgb = COLOR_ACCENT
                bar.line.fill.background()

                # Card Text Box
                card_tf_box = slide.shapes.add_textbox(
                    Inches(left_pos + 0.25), Inches(card_top + 0.35),
                    Inches(card_width - 0.5), Inches(card_height - 0.6)
                )
                tf_card = card_tf_box.text_frame
                tf_card.word_wrap = True

                # Card Header
                p_card_title = tf_card.paragraphs[0]
                p_card_title.text = card["title"]
                p_card_title.font.name = "Arial"
                p_card_title.font.size = Pt(18 if num_cards <= 3 else 16)
                p_card_title.font.bold = True
                p_card_title.font.color.rgb = COLOR_PRIMARY
                p_card_title.space_after = Pt(14)

                # Card Body
                p_card_body = tf_card.add_paragraph()
                p_card_body.text = card["text"]
                p_card_body.font.name = "Arial"
                p_card_body.font.size = Pt(13 if num_cards <= 3 else 12)
                p_card_body.font.color.rgb = COLOR_TEXT
                p_card_body.line_spacing = 1.35

    prs.save(str(output_path))
    print(f"[OK] Successfully built 10-slide PowerPoint presentation at: {output_path}")


if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent / "Packet_Tracer_IP_Planner_Presentation.pptx"
    build_presentation(out_file)
