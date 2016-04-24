#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    # TODO: put package requirements here
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='with-venv',
    version='0.0.1',
    description="Context manager controls venv allowing functions to be run in a different interpreter.",
    long_description=readme + '\n\n' + history,
    author="Andrew B Godbehere",
    author_email='andrew.godbehere@sumupanalytics.com',
    url='https://github.com/agodbehere/with-venv',
    packages=[
        'with_venv',
    ],
    package_dir={'with_venv':
                 'with_venv'},
    include_package_data=True,
    install_requires=requirements,
    license="ISCL",
    zip_safe=True,
    keywords='with-venv',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
