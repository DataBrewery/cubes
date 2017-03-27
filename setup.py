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
        'console_scripts': [
            'slicer = cubes.slicer.commands:main'
        ],
        "authenticators": [
            "admin_admin = cubes.server.auth:AdminAdminAuthenticator",
            "pass_parameter = cubes.server.auth:PassParameterAuthenticator",
            "http_basic_proxy = cubes.server.auth:HTTPBasicProxyAuthenticator",
        ],
        "authorizers": [
            "simple = cubes.auth:SimpleAuthorizer",
        ],
        "browsers": [
            "sql":"cubes.sql.browser:SQLBrowser",
            "slicer":"cubes.server.browser:SlicerBrowser",
        ],
        "formatters": [
            "cross_table = cubes.formatters:CrossTableFormatter",
            "csv = cubes.formatters:CSVFormatter",
            'xlsx': 'cubes.formatters:XLSXFormatter',
            "html_cross_table = cubes.formatters:HTMLCrossTableFormatter",
        ],
        "providers": [
            "default":"cubes.metadata.providers:StaticModelProvider",
            "slicer":"cubes.server.store:SlicerModelProvider",
        ],
        "request_log_handlers": [
            "default = cubes.server.logging:DefaultRequestLogHandler",
            "csv = cubes.server.logging:CSVFileRequestLogHandler",
            'xlsx': 'cubes.server.logging:XLSXFileRequestLogHandler',
            "json = cubes.server.logging:JSONRequestLogHandler",
            "sql = cubes.sql.logging:SQLRequestLogger",
        ],
        "stores": [
            "sql":"cubes.sql.store:SQLStore",
            "slicer":"cubes.server.store:SlicerStore",
        ],
    },

    test_suite="tests",

    keywords = "olap multidimensional data analysis",

    # could also include long_description, download_url, classifiers, etc.
)
