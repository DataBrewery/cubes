import application_controller
        
class ModelController(application_controller.ApplicationController):

    def show(self):
        d = self.model.to_dict(with_mappings = False)

        # Add available model locales based on server configuration
        d["locales"] = self.app.locales;
        return self.json_response(d)

    def dimension(self):
        dim_name = self.params["name"]

        dim = self.model.dimension(dim_name)
        return self.json_response(dim.to_dict())

    def _cube_dict(self, cube):
        d = cube.to_dict(expand_dimensions = True, 
                         with_mappings = False,
                         full_attribute_names = True
                         )

        return d

    def get_default_cube(self):
        return self.json_response(self._cube_dict(self.cube))

    def get_cube(self):
        cube_name = self.params["name"]

        cube = self.model.cube(cube_name)
        return self.json_response(self._cube_dict(cube))
        
    def dimension_levels(self):
        dim_name = self.params["name"]
        dim = self.model.dimension(dim_name)
        levels = [l.to_dict() for l in dim.default_hierarchy.levels]

        string = json.dumps(levels)

        return Response(string)

    def dimension_level_names(self):
        dim_name = self.params["name"]
        dim = self.model.dimension(dim_name)

        return self.json_response(dim.default_hierarchy.level_names)
