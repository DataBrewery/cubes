import sys
from setuptools import setup, find_packages

requirements = [
    "python-dateutil",
    "jsonschema",
    "expressions>=0.2.3"
]

extras = {
    'sql': 'sqlalchemy>= 0.9.0',
    'slicer': 'werkzeug',
    'html': 'jinja',
    'all': ['cubes[%s]' % extra for extra in ['sql','slicer','html']],
    'dev': ['cubes[all]', 'sphinx'],
}

setup(
    name = "cubes",
    version = '1.1',

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires = requirements,
    extras_require = extras,

    packages = find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),

    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.txt', '*.rst'],
        'cubes': ['templates/*.html', 'templates/*.js', 'schemas/*.json'],
        'cubes.server': ['templates/*.html'],
    },

    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python',
        'Topic :: Database',
        'Topic :: Scientific/Engineering',
        'Topic :: Utilities'
    ],

    entry_points={
        'console_scripts': ['slicer = cubes.slicer.commands:main'],
    },

    test_suite = "tests",

    # metadata for upload to PyPI
    author = "Stefan Urbanek",
    author_email = "stefan.urbanek@gmail.com",
    description = "Lightweight framework for Online Analytical Processing (OLAP) and multidimensional analysis",
    license = "MIT license with following addition: If your version of the Software supports interaction with it remotely through a computer network, the above copyright notice and this permission notice shall be accessible to all users.",
    keywords = "olap multidimensional data analysis",
    url = "http://cubes.databrewery.org"

    # could also include long_description, download_url, classifiers, etc.
)

