# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


requirements = [
    'jsonschema',
    'sqlalchemy',
]

setup(
    name='cubes_lite',
    version='0.1',

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires=requirements,

    packages=find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']),

    package_data={
        # If any package contains *.txt or *.rst files, include them:
        'cubes_lite': ['model/schemas/*.json'],
    },

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python',
        'Topic :: Database',
        'Topic :: Scientific/Engineering',
        'Topic :: Utilities'
    ],

    entry_points={},
    test_suite='tests',
)
