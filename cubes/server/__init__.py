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
    if config.has_option("server", "host"):
        host = config.get("server", "host")
    else: 
        host = "localhost"
    
    
    if config.has_option("server", "port"):
        port = config.getint("server", "port")
    else:
        port = 5000

    if config.has_option("server", "reload"):
        use_reloader = config.getboolean("server", "reload")
    else:
        use_reloader = False

    application = Slicer(config)
    werkzeug.serving.run_simple(host, port, application, use_reloader = use_reloader)
    
