# -*- encoding: utf-8 -*-

# TODO: This is very preliminary interface of the server. Just follows the
# original Cubes 1.x server initialization.

class SlicerServer:
    __extension_type__ = "server"
    __extension_suffix__ = "Server"
   
    config_file: str
    debug: bool

    def __init__(self, config_file: str, debug: bool=False) -> None:
        self.config_file = config_file
        self.debug = debug

    def run(self) -> None:
        """Run the server."""
        raise NotImplementedError("Subclasses of slicer server should "
                                  "implement the `run()` method")

