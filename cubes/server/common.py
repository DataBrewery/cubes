"""Common objects for slicer server"""

try:
    from werkzeug.exceptions import HTTPException
except:
    # No need to bind objects here to dependency-sink, as the user
    # will be notified when he tries to use Slicer or run_server about
    # the missing package
    HTTPException = object

import json
import os.path
import decimal
import datetime

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates')

VERSION = "0.7"
API_VERSION = "1"

class ServerError(HTTPException):
    code = 500
    error_type = "default"
    def __init__(self, message = None, exception = None):
        super(ServerError, self).__init__()
        self.message = message
        self.exception = exception
        self.details = {}

    def get_body(self, environ):
        error = {
            "message": self.message,
            "type": self.__class__.error_type
        }

        if self.exception:
            error["reason"] = str(self.exception)

        if self.details:
            error.update(self.details)
        
        string = json.dumps({"error": error},indent = 4)
        return string

    def get_headers(self, environ):
        """Get a list of headers."""
        return [('Content-Type', 'application/json')]

class RequestError(ServerError):
    error_type = "request"
    code = 400

class NotFoundError(ServerError):
    code = 404
    error_type = "not_found"
    def __init__(self, obj, objtype = None, message = None):
        super(NotFoundError, self).__init__(message)
        self.details = {
            "object": obj,
        }
        if not message:
            self.message = "Object '%s' of type '%s' was not found" % (obj, objtype)
        if type:
            self.details["object_type"] = objtype

class AggregationError(ServerError):
    code = 400

class SlicerJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        """Creates a JSON encoder that will convert some data values and also allows
        iterables to be used in the object graph.

        :Attributes:
        * `iterator_limit` - limits number of objects to be fetched from iterator. Default: 1000.
        """

        super(SlicerJSONEncoder, self).__init__(*args, **kwargs)

        self.iterator_limit = 1000

    def default(self, o):
        if type(o) == decimal.Decimal:
            return float(o)
        if type(o) == datetime.date or type(o) == datetime.datetime:
            return o.isoformat()
        if hasattr(o, "as_dict") and callable(getattr(o, "as_dict")):
            return o.as_dict()
        else:
            array = None
            try:
                # If it is an iterator, then try to construct array and limit number of objects
                iterator = iter(o)
                count = self.iterator_limit
                array = []
                for obj in iterator:
                    array.append(obj)
                    count -= 1
                    if count <= 0:
                        break
            except TypeError as e:
                # not iterable
                pass

            if array is not None:
                return array
            else:
                return json.JSONEncoder.default(self, o)
