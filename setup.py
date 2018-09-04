# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from setuptools import setup, find_packages


requirements = [
    'python-dateutil',
    'jsonschema',
    'sqlalchemy',
]

extras = {
    'dev': ['cubes_lite', 'sphinx'],
}

setup(
    name='cubes_lite',
    version='0.1',

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires=requirements,
    extras_require=extras,

    packages=find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']),

    package_data={
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.txt', '*.rst'],
        'cubes_lite': ['schemas/*.json'],
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
