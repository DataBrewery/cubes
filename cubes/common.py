import logging

logger_name = "cubes"
    
def _configure_logger():
    logger = logging.getLogger(logger_name)
    # logger.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s')
            # datefmt='%a, %d %b %Y %H:%M:%S',
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
