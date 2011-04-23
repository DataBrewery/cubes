import application_controller
import cubes

class CubesController(application_controller.ApplicationController):
    def initialize(self):
        super(CubesController, self).initialize()
        self.initialize_cube()
        
    def finalize(self):
        self.finalize_cube()
    
    def prepare_cuboid(self):
        cut_string = self.request.args.get("cut")

        if cut_string:
            cuts = cubes.cuts_from_string(cut_string)
        else:
            cuts = []

        self.cuboid = cubes.Cuboid(self.browser, cuts)
        
    def aggregate(self):
        self.prepare_cuboid()

        drilldown = self.request.args.getlist("drilldown")

        result = self.cuboid.aggregate(drilldown = drilldown, 
                                        page = self.page, 
                                        page_size = self.page_size,
                                        order = self.order)

        # return Response(result.as_json())
        return self.json_response(result)

    def facts(self):
        self.prepare_cuboid()

        result = self.cuboid.facts(order = self.order,
                                    page = self.page, 
                                    page_size = self.page_size)

        return self.json_response(result)

    def fact(self):
        fact_id = self.params["id"]

        fact = self.browser.fact(fact_id)

        if fact:
            return self.json_response(fact)
        else:
            return self.error("No fact with id=%s" % fact_id, status = 404)
        
    def values(self):
        self.prepare_cuboid()

        dim_name = self.params["dimension"]
        depth_string = self.request.args.get("depth")
        if depth_string:
            try:
                depth = int(self.request.args.get("depth"))
            except:
                return common.RequestError("depth should be an integer")
        else:
            depth = None
        
        try:
            dimension = self.cube.dimension(dim_name)
        except:
            return common.NotFoundError(dim_name, "dimension", 
                                        message = "Dimension '%s' was not found" % dim_name)

        values = self.cuboid.values(dimension, depth = depth, page = self.page, page_size = self.page_size)

        result = {
            "dimension": dimension.name,
            "depth": depth,
            "data": values
        }
        
        return self.json_response(result)
    
    def report(self):
        """Create multi-query report response."""
        self.prepare_cuboid()
        
        report_request = self.json_request()
        
        result = self.browser.report(self.cuboid, report_request)
        
        return self.json_response(result)
    
