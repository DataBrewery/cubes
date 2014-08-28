Cubes Visualizer
================

Cubes Visualizer is an application for browsing and visualizing data from a
cubes Slicer server.


Use
---

Primary use:

1. have a slicer server running – remotely or locally
2. open the visualizer index file in your browser. The file is located in the
   source directory in `cubes/server/visualizer/index.html `
3. Specify the slicer URL. `http://localhost:5000` is the default.


Note: this stand-alone static page is the intended use of the visualizer.


Alternative use (linked with the server):

1. run the slicer with `--visualizer default` option and open
   `http://localhost:5000/visualizer`. Confirm the default URL.

Note: might be changed in the future.


Deployment
----------

1. Copy the static files `cubes/server/visualizer` to desired location.
2. Specify slicer URL.


Note: you might connect to any slicer server, for example:
`http://slicer-demo.herokuapp.com`


Authors:

* Ryan Berlew (rberlew at github: https://github.com/rberlew)
* Robin Thomas (robin900 at github: https://github.com/robin900)

