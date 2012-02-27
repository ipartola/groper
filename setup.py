#!/usr/bin/env python

from setuptools import setup

from groper import __version__ as VERSION

setup(
    name = 'groper',
    version = VERSION,
    description = 'Library for parsing config files and command line arguments',
    author = 'Igor Partola',
    author_email = 'igor@igorpartola.com',
    url = 'https://github.com/ipartola/groper',
    py_modules = ['groper'],
    license = 'MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries',
    ],
)
