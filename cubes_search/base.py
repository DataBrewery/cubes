import whoosh_engine
import sphinx

def create_searcher(engine, browser, **options):
    if engine == 'sphinx':
        iclass = sphinx.SphinxSearcher
    elif engine == 'whoosh':
        iclass = whoosh_engine.WhooshSearcher
    else:
        raise Exception('Unknown search engine %s' % engine)

    return iclass(browser, **options)

