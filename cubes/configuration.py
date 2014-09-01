import os
import configparser

def _interpolate(self, parser, section, option, value, *defaults):
    try:
        return value % os.environ
    except KeyError:
        raise EnvironmentVariableMissingError\
              (option, section, value)

class EnvironmentVariableMissingError(configparser.InterpolationError):
    """A string substitution required a setting which was not available."""

    def __init__(self, option, section, rawval):
        msg = ("Bad value substitution:\n"
               "\tsection: [%s]\n"
               "\toption : %s\n"
               "\trawval : %s\n"
               % (section, option, rawval))
        configparser.InterpolationError.__init__(self, option, section, msg)

class EnvironmentInterpolation(configparser.Interpolation):
    """Interpolate from the environment"""

    before_get = _interpolate
    before_set = _interpolate
   #before_read = _interpolate
   #before_write = _interpolate


class EnvironmentConfigParser(configparser.ConfigParser):
    _DEFAULT_INTERPOLATION = EnvironmentInterpolation()
