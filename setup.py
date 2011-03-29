from setuptools import setup, find_packages

setup(
    name = "cubes",
    version = '0.5.0',

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires = [],

    packages=find_packages(exclude=['ez_setup']),
    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.txt', '*.rst'],
        'cubes.server': ['templates/*.html']
    },

    scripts = ['bin/slicer'],
    
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python',
        'Topic :: Database',
        'Topic :: Scientific/Engineering',
        'Topic :: Utilities'
    ],
    
    test_suite = "cubes.tests.test_suite",

    # metadata for upload to PyPI
    author = "Stefan Urbanek",
    author_email = "stefan.urbanek@gmail.com",
    description = "Framework for Online Analytical Processing (OLAP), multidimensional analysis and cube precomputation",
    license = "GPL",
    keywords = "olap multidimensional data analysis",
    url = "http://databrewery.org"

    # could also include long_description, download_url, classifiers, etc.
)
