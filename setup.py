import sys
from setuptools import setup, find_packages

requirements = []
if sys.version_info < (2,7):
    requirements += ['ordereddict']

setup(
    name = "cubes",
    version = '0.10',

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires = requirements,

    packages=find_packages(exclude=['ez_setup']),
    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.txt', '*.rst'],
        'cubes.server': ['templates/*.html']
    },

    scripts = ['bin/slicer'],

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
    description = "Lightweight framework for Online Analytical Processing (OLAP) and multidimensional analysis",
    license = "MIT license with following addition: If your version of the Software supports interaction with it remotely through a computer network, the above copyright notice and this permission notice shall be accessible to all users.",
    keywords = "olap multidimensional data analysis",
    url = "http://databrewery.org"

    # could also include long_description, download_url, classifiers, etc.
)
