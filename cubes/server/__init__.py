from application import *
try:
    import werkzeug.serving
except:
    pass

__all__ = {
    "Slicer",
    "serve"
}

def run_server(config):
    """Run OLAP server with configuration specified in `config`"""
    host = config["host"] if "host" in config else "localhost"
    port = config["port"] if "port" in config else "5000"
    use_reloader = config["reload"] if "reload" in config else False

    application = Slicer(config)
    werkzeug.serving.run_simple(host, port, application, use_reloader = use_reloader)
    
