"""Runner script to launch the Cisco Packet Tracer IP Planner web interface."""

import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from web.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n==================================================================")
    print(f"  Starting Cisco Packet Tracer IP Planner Web Interface")
    print(f"  Open your browser at: http://127.0.0.1:{port}")
    print(f"==================================================================\n")
    app.run(host="127.0.0.1", port=port, debug=False)
