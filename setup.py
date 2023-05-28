#!/usr/bin/env python3
from setuptools import setup

classifiers = """
"""

setup(name='pitchtools',
      version='1.11.0',
      python_requires=">=3.9",
      description='Utilities to convert between midinotes, frequency and notenames', 
      long_description=open('README.rst').read(),
      classifiers=list(filter(None, classifiers.split('\n'))),
      author='Eduardo Moguillansky',
      author_email='eduardo.moguillansky@gmail.com',
      packages=['pitchtools'],
      package_data={'pitchtools': ['py.typed']},
      url="https://github.com/gesellkammer/pitchtools"
)


