++++++++
Backends
++++++++


Implementing Backend
====================

To implement custom backend:

* create a subclass of Workspace
* provide `create_workspace(model, *args, *kwargs)` method in the workspace
  module that returns an instance of `Worskspace` subclass
* in `Workspace` subclass implement `browser(cube, locale)` method and use
  `localized_model(locale)` to get model
* implement subclass of `AggregationBrowser`


