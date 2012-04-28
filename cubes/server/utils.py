# Soft dependency on Werkzeug
try:
    from werkzeug.local import Local, LocalManager
    from werkzeug.routing import Map, Rule

    local = Local()
    local_manager = LocalManager([local])

except:
    from cubes.common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Local = LocalManager = _missing
    Map = Rule = _missing

    local = _missing
    local_manager = _missing
