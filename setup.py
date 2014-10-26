#!/usr/bin/env python

import openassets
import os
import setuptools

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()

setuptools.setup(
    name = 'openassets',
    version = openassets.__version__,
    packages = [ 'openassets' ],
    description = 'Reference implementation of the Open Assets Protocol',
    author = 'Flavien Charlon',
    author_email = 'flavien@charlon.net',
    url = 'https://github.com/OpenAssets/openassets',
    license = 'MIT License',
    install_requires = [
        'python-bitcoinlib == 0.2.1'
    ],
    test_suite = 'tests',
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)