from common import API_VERSION

try:
    from werkzeug import __version__ as werkzeug_version
    from slicer import Slicer, run_server, create_server
except ImportError:
    from cubes.common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Slicer = _missing
    run_server = _missing
    create_server = _missing

try:
    from blueprint import SlicerBlueprint
except ImportError:
    from cubes.common import MissingPackage
    _missing = MissingPackage("flask", "Slicer blueprint")
    SlicerBlueprint = _missing

__all__ = (
    "Slicer",
    "run_server",
    "create_server",
    "API_VERSION"
)
