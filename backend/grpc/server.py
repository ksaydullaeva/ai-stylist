"""
Standalone gRPC server for the Stylist service.
Usage (from backend/): python grpc/server.py [port]
Note: `python -m grpc.server` does NOT work — after the proxy loads the real
grpc library, `grpc.server` resolves to the real grpc's server submodule.
Run the file directly instead.
"""

import importlib.util
import sys
from pathlib import Path

# Make backend/ and backend/grpc/generated/ importable for stylist_pb2 / stylist_pb2_grpc
_backend = Path(__file__).resolve().parent.parent
_generated = Path(__file__).resolve().parent / "generated"
for _p in (_backend, _generated):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import grpc
from concurrent import futures

import stylist_pb2_grpc

# Import our servicer via absolute file path — sys.modules['grpc'] is now the
# real grpc library, so 'from grpc.servicer import ...' would resolve to the
# wrong package.  We load the file directly instead.
_servicer_file = Path(__file__).resolve().parent / "servicer.py"
_spec = importlib.util.spec_from_file_location("_stylist_servicer", _servicer_file)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
StylistServicer = _mod.StylistServicer


def serve(port: int = 50051) -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    stylist_pb2_grpc.add_StylistServicer_to_server(StylistServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC server listening on [::]:{port}")
    server.wait_for_termination()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 50051
    serve(port=port)
