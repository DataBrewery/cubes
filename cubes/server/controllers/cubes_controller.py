from werkzeug.wrappers import Response
import application_controller
import cubes
from .. import common

import cStringIO
import csv
import codecs

class CSVGenerator(object):
    def __init__(self, records, fields, include_header = True, 
                dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.include_header = include_header
        self.records = records
        self.fields = fields
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.encoder = codecs.getincrementalencoder(encoding)()
    
    def csvrows(self):
        if self.include_header:
            yield self._row_string(self.fields)

        for record in self.records:
            row = []
            for field in self.fields:
                value = record.get(field)
                if type(value) == unicode or type(value) == str:
                    row.append(value.encode("utf-8"))
                elif value:
                    row.append(unicode(value))
                else:
                    row.append(None)

            yield self._row_string(row)
    
    def _row_string(self, row):
        self.writer.writerow(row)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # empty queue
        self.queue.truncate(0)

        return data
    
class UnicodeCSVWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.

    From: <http://docs.python.org/lib/csv-examples.html>
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        new_row = []
        for value in row:
            if type(value) == unicode or type(value) == str:
                new_row.append(value.encode("utf-8"))
            elif value:
                new_row.append(unicode(value))
            else:
                new_row.append(None)
                
        self.writer.writerow(new_row)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

class CubesController(application_controller.ApplicationController):
    def initialize(self):
        # FIXME: remove this (?)
        cube_name = self.params.get("cube")
        if not cube_name:
            cube_name = self.config.get("model", "cube")
            
        self.logger.info("browsing cube '%s' (locale: %s)" % (cube_name, self.locale))
        self.cube = self.model.cube(cube_name)
        self.browser = self.app.workspace.browser_for_cube(self.cube, self.locale)
        
    def prepare_cell(self):
        cut_string = self.args.get("cut")

        if cut_string:
            self.logger.debug("preparing cell for cut string: '%s'" % cut_string)
            cuts = cubes.cuts_from_string(cut_string)
        else:
            self.logger.debug("preparing cell for whole cube")
            cuts = []

        self.cell = cubes.Cell(self.cube, cuts)
        
    def aggregate(self):
        self.prepare_cell()

        drilldown = self.args.getlist("drilldown")

        dic_drilldown = {}

        # Allow dimension:level specification for drilldown

        if drilldown:
            for drill_dim in drilldown:
                split = drill_dim.split(":")
                dic_drilldown[split[0]] = split[1] if len(split) >= 2 else None
        
        result = self.browser.aggregate(self.cell, drilldown = dic_drilldown, 
                                        page = self.page, 
                                        page_size = self.page_size,
                                        order = self.order)

        # return Response(result.as_json())
        return self.json_response(result)

    def facts(self):
        self.prepare_cell()

        format = self.args.get("format")
        if format:
            format = format.lower()
        else:
            format = "json"

        fields_str = self.args.get("fields")
        if fields_str:
            fields = fields_str.lower().split(',')
        else:
            fields = None

        result = self.cell.facts(order = self.order,
                                    page = self.page, 
                                    page_size = self.page_size)

        if format == "json":
            return self.json_response(result)
        elif format == "csv":
            if not fields:
                fields = result.field_names()
            generator = CSVGenerator(result, fields)
            return Response(generator.csvrows(), 
                            mimetype='text/csv')
        else:
            raise common.RequestError("unknown response format '%s'" % format)

    def fact(self):
        fact_id = self.params["id"]

        fact = self.browser.fact(fact_id)

        if fact:
            return self.json_response(fact)
        else:
            return self.error("No fact with id=%s" % fact_id, status = 404)
        
    def values(self):
        self.prepare_cell()

        dim_name = self.params["dimension"]
        depth_string = self.args.get("depth")
        if depth_string:
            try:
                depth = int(self.args.get("depth"))
            except:
                return common.RequestError("depth should be an integer")
        else:
            depth = None
        
        try:
            dimension = self.cube.dimension(dim_name)
        except:
            return common.NotFoundError(dim_name, "dimension", 
                                        message = "Dimension '%s' was not found" % dim_name)

        values = self.cell.values(dimension, depth = depth, page = self.page, page_size = self.page_size)

        result = {
            "dimension": dimension.name,
            "depth": depth,
            "data": values
        }
        
        return self.json_response(result)
    
    def report(self):
        """Create multi-query report response."""
        self.prepare_cell()
        
        report_request = self.json_request()
        
        result = self.browser.report(self.cell, report_request)
        
        return self.json_response(result)
    
