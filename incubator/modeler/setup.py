import sys
from setuptools import setup, find_packages

requirements = ["flask"]

setup(
    name = "cubes_modeler",
    version = '0.1',

    install_requires = requirements,

    packages = find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    package_data = {
        'cubes_modeler': [
            'templates/*',
            'static/*.js',
            'static/js/*.js',
            'static/fonts/*',
            'static/css/*.css',
            'static/views/*.html',
            'static/views/partials/*.html'
         ]
    },

    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Database',
        'Topic :: Scientific/Engineering',
        'Topic :: Utilities'
    ],

    test_suite = "tests",

    # metadata for upload to PyPI
    author = "Stefan Urbanek",
    author_email = "stefan.urbanek@gmail.com",
    description = "Model editor for Cubes OLAP",
    license = "MIT license",
    keywords = "olap multidimensional data analysis",
    url = "http://cubes.databrewery.org"
)

