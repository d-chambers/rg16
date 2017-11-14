#!/usr/bin/env python
# -*- coding: utf-8 -*-
# from detex.version import __version__
from glob import glob
from os.path import join, abspath, dirname

from setuptools import setup

here = dirname(abspath(__file__))

datasets = [x for x in glob(join(here, 'rg16', 'datasets', '**', '*'))
            if not (x.endswith('.py') or x.endswith('.pyc'))]

# get version without importing detex
with open(join(here, 'rg16', 'version.py'), 'r') as fi:
    content = fi.read().split('=')[-1].strip()
    __version__ = content.replace('"', '').replace("'", '')


with open('README.md') as readme_file:
    readme = readme_file.read()


requirements = [
    'obspy',
    'numpy',
]

test_requirements = [
    'pytest'
]

setup_requirements = []

entry_points = {
    'obspy.plugin.waveform': [
        'RG16 = obspy.io.ascii.core',
    ],
    'obspy.plugin.waveform.RG16': [
        'isFormat = rg16.core:is_rg16',
        'readFormat = rg16.core:read_rg16',
    ]
}

packages = [
    'rg16',
]

setup(
    name='rg16',
    version=__version__,
    description="a library for working with fairfield nodal data",
    long_description=readme,
    author="Derrick Chambers",
    author_email='djachambeador@gmail.com',
    url='https://bitbucket.org/smrd/rg16',
    packages=packages,
    package_dir={'rg16': 'rg16'},
    include_package_data=True,
    install_requires=requirements,
    license="BSD",
    zip_safe=False,
    keywords='rg16',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=test_requirements,
    setup_requires=setup_requirements,
    entry_points=entry_points,
    data_files=datasets,
)
