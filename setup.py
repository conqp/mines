#! /usr/bin/env python
"""Installation script."""

from setuptools import setup

setup(
    name='mines',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    author='Richard Neumann',
    author_email='mail@richard-neumann.de',
    python_requires='>=3.9',
    py_modules=['mines'],
    entry_points={'console_scripts': ['pymines = mines:main'],},
    url='https://github.com/conqp/mines',
    license='GPLv3',
    description='A mine sweeping game for the terminal.',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    keywords='mine sweeper minesweeper python console terminal'
)
