"""StyleAI gRPC transport layer.

This package is physically named 'grpc/' to co-locate all gRPC-related files.
Because the folder name shadows the installed grpc library, this __init__.py
installs a lazy proxy in sys.modules so every caller of `import grpc` receives
the real library on first attribute access.

Why lazy loading?
-----------------
Calling exec_module (or import_module) for site-packages/grpc from *within*
our own exec_module call causes infinite recursion in Python 3.14: the new
`_initializing` flag in _find_and_load means that every submodule import
inside grpc's __init__ re-triggers a fresh load of the parent 'grpc' package,
which finds this file again.

By deferring the load to __getattr__ (which runs *after* our exec_module
returns and no 'grpc' module lock is held), the import machinery can complete
the real grpc init without interference.
"""

import os
import sys
import types


class _GrpcProxy(types.ModuleType):
    """Lazy proxy: loads site-packages/grpc on first attribute access."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._loaded = False

    def _load_real(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        # __file__ is backend/grpc/__init__.py; we want backend/ (one level up)
        _backend = os.path.normpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        def _is_backend(p: str) -> bool:
            return os.path.normpath(os.path.abspath(p) if p else os.getcwd()) == _backend

        # Temporarily hide backend/ so the real site-packages/grpc is found.
        _removed = [(i, p) for i, p in enumerate(sys.path) if _is_backend(p)]
        for _i, _ in reversed(_removed):
            sys.path.pop(_i)
        for _key in list(sys.path_importer_cache):
            if _is_backend(_key):
                del sys.path_importer_cache[_key]

        # Remove our proxy so `import grpc` below triggers a fresh load.
        del sys.modules["grpc"]
        try:
            import grpc as _real  # type: ignore[import]  # resolves to site-packages
            sys.modules["grpc"] = _real
            # Mirror all real grpc attributes onto this proxy so that existing
            # references (e.g. `grpc` variables held by callers) keep working.
            self.__dict__.update(_real.__dict__)
        finally:
            for _i, _p in _removed:
                sys.path.insert(_i, _p)

    def __getattr__(self, name: str):
        self._load_real()
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"module 'grpc' has no attribute {name!r}") from None

    def __repr__(self) -> str:
        return f"<grpc lazy proxy, loaded={self._loaded}>"


sys.modules["grpc"] = _GrpcProxy("grpc")
