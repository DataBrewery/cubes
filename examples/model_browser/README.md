Model Browser
=============

Example Flask web application for browsing a model.

Use:

    python application.py slicer.ini

Where slicer.ini should contain absolute paths for model, translations. If you
are using sqlite database then URL should be absolute as well.

You can try it with the hello_world example:

    cd ../hellow_world
    python ../model_browser/application.py slicer.ini

And then navigate your browser to: http://localhost:5000
