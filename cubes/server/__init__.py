from common import API_VERSION

try:
    from werkzeug import __version__ as werkzeug_version
    from slicer import Slicer, run_server

except ImportError:
    from cubes.common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Slicer = run_server = _missing

__all__ = (
    "Slicer",
    "run_server",
    "API_VERSION"
)
