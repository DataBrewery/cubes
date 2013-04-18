from cubes.workspace import Workspace, get_backend, config_items_to_dict

def create_workspace(model, **options):
    return CompositeWorkspace(model, **options)

class CompositeWorkspace(Workspace):
    def __init__(self, model, config, **options):
        super(CompositeWorkspace, self).__init__(model, **options)
        self.workspaces = {}
        self.config = config

    def __str__(self):
        return 'CompositeWorkspace(%s)' % str(self.model)

    def browser(self, cube, locale=None):
        workspace = self.workspace_for_cube(cube)

        model = self.localized_model(locale)
        return workspace.browser(cube, locale=locale)

    def workspace_for_cube(self, cube):
        datasource = cube.info.get('datasource') or self.model.info.get('datasource')
        if datasource in self.workspaces:
            return self.workspaces[datasource]
        # look up config section in config
        ds_config = config_items_to_dict(self.config.items(datasource))
        if not ds_config:
            raise ValueError("Can't find config section named %s" % datasource)
        # get backend
        backend = get_backend(ds_config.get('backend'))
        wksp = backend.create_workspace(self.model, **ds_config)
        self.workspaces[datasource] = wksp
        return wksp


