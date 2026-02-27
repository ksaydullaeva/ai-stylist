"""
Run the gRPC server for the Stylist service.
Usage (from repo root): python -m backend.grpc_server
Or from backend/: PYTHONPATH=.:generated python grpc_server.py
"""
import sys
from pathlib import Path

# Ensure backend and backend/generated are on path for stylist_pb2 / stylist_pb2_grpc
_backend = Path(__file__).resolve().parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))
if str(_backend / "generated") not in sys.path:
    sys.path.insert(0, str(_backend / "generated"))

import grpc
from concurrent import futures

from generated import stylist_pb2_grpc
from grpc_servicer import StylistServicer


def serve(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    stylist_pb2_grpc.add_StylistServicer_to_server(StylistServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC server listening on [::]:{port}")
    server.wait_for_termination()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 50051
    serve(port=port)
