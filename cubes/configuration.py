import os
import configparser

class EnvironmentInterpolation(configparser.Interpolation):
    """Interpolate from the environment"""

    def before_get(self, parser, section, option, value, defaults):
        return value % os.environ

    def before_set(self, parser, section, option, value):
        return value % os.environ

    def before_read(self, parser, section, option, value):
        return value % os.environ

    def before_write(self, parser, section, option, value):
        return value % os.environ


class EnvironmentConfigParser(configparser.ConfigParser):
    _DEFAULT_INTERPOLATION = EnvironmentInterpolation()
