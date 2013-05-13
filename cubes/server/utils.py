import pytz
from time import gmtime, strftime
from datetime import datetime, timedelta

tz_utc = pytz.timezone('UTC')
default_tz = pytz.timezone(strftime("%Z", gmtime()))


def now(tzinfo=default_tz):
    n = datetime.utcnow()
    n = tz_utc.localize(n)
    return n.astimezone(tzinfo)


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
