"""
Generate Python gRPC code from backend/proto/stylist.proto.
Run from repo root: python backend/scripts/generate_grpc.py
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROTO_DIR = REPO_ROOT / "backend" / "proto"
OUT_DIR = REPO_ROOT / "backend" / "generated"
PROTO_FILE = PROTO_DIR / "stylist.proto"

OUT_DIR.mkdir(parents=True, exist_ok=True)

cmd = [
    sys.executable,
    "-m",
    "grpc_tools.protoc",
    f"-I{PROTO_DIR}",
    f"--python_out={OUT_DIR}",
    f"--grpc_python_out={OUT_DIR}",
    str(PROTO_FILE),
]
subprocess.run(cmd, check=True)
print("Generated:", list(OUT_DIR.glob("*.py")))
