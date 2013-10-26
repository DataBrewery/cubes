try:
    from blueprint import slicer, API_VERSION
    from base import run_server, create_server
except ImportError:
    from ..common import MissingPackage
    _missing = MissingPackage("flask", "Slicer server")
    slicer = _missing
    run_server = _missing
    create_server = _missing
    API_VERSION = "unknown"


__all__ = (
    "slicer",
    "run_server",
    "create_server",
    "API_VERSION"
)
