"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


requirements = [
    "python-dateutil",
    "jsonschema",
    "expressions>=0.2.3",
    "sqlalchemy>0.9.0",
    "click",
]

extras = {
    'slicer': 'werkzeug',
    'html': 'jinja',
    'all': ['cubes[%s]' % extra for extra in ['slicer', 'html']],
    'dev': ['cubes[all]', 'sphinx'],
}

setup(
    name = "cubes",

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version = '2.0',

    description = "Lightweight framework for Online Analytical Processing (OLAP) and multidimensional analysis",
    long_description=long_description,
    url = "http://cubes.databrewery.org",

    # Author details
    author = "Stefan Urbanek",
    author_email = "stefan.urbanek@gmail.com",
    license = "MIT",

    install_requires = requirements,
    extras_require = extras,

    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),

    package_data={
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.txt', '*.rst'],
        'cubes': ['templates/*.html', 'templates/*.js', 'schemas/*.json'],
        'cubes.server': ['templates/*.html'],
    },

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',

        'Topic :: Database',
        'Topic :: Scientific/Engineering',
        'Topic :: Utilities'

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],

    entry_points={
        'console_scripts': [ 'slicer = cubes.slicer.commands:main' ],
    },

    test_suite="tests",

    keywords = "olap multidimensional data analysis",

    # could also include long_description, download_url, classifiers, etc.
)
