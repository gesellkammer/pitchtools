#!/usr/bin/env python3
"""
This module provides a set of functions to work with musical pitch. It enables
to convert between frequenies, midinotes and notenames

==========
Pitchtools
==========

This module provides a set of functions to work with musical pitch. It enables
to convert between frequenies, midinotes and notenames

Examples
========

Convert some note names to frequencies

.. code-block:: python

    >>> from pitchtools import *
    >>> ebscale = "4Eb 4F 4G 4Ab 4Bb 5C 5D".split()
    >>> for note in ebscale:
    ...     freq = n2f(note)
    ...     midinote = f2m(freq)
    ...     print(f"{note} = {freq:.1f}Hz (midinote = {midinote})")
    4Eb = 312.5 Hz (midi = 63.0)
    4F  = 350.8 Hz (midi = 65.0)
    4G  = 393.7 Hz (midi = 67.0)
    4Ab = 417.2 Hz (midi = 68.0)
    4Bb = 468.3 Hz (midi = 70.0)
    5C  = 525.6 Hz (midi = 72.0)
    5D  = 590.0 Hz (midi = 74.0)
    
    
    
The same but with a different reference frequency


.. code-block:: python


    from pitchtools import *
    ebscale = "4Eb 4F 4G 4Ab 4Bb 5C 5D".split()
    cnv = Converter(a4=435)
    for note in ebscale:
        # Convert to frequency with default a4=442 Hz
        freq = cnv.n2f(note)
        midinote = cnv.[Of2m(freq)
        print(f"{note} = {freq} Hz (midinote = {midinote})")


Microtones
~~~~~~~~~~

.. code-block:: python

    >>> from pitchtools import *
    >>> n2m("4C+")
    60.5
    >>> n2m("4Db-10")
    60.9
    >>> m2n(61.2)
    4C#+20


**Microtonal notation**


+---------+---------+
| Midinote| Notename|
|         |         |
+=========+=========+
| 60.25   | 4C+25 / |
|         | 4C>     |
+---------+---------+
| 60.45   | 4C+45   |
+---------+---------+
| 60.5    | 4C      |
+---------+---------+
| 60.75   | 4Db-25  |
+---------+---------+
| 61.5    | 4D-     |
+---------+---------+
| 61.80   | 4D-20   |
+---------+---------+
| 63      | 4D#     |
+---------+---------+
| 63.5    | 4D#+    |
+---------+---------+
| 63.7    | 4E-30   |
+---------+---------+

"""
from setuptools import setup

classifiers = """
"""

setup(name='pitchtools',
      version='1.0.3',
      description='Utilities to convert between midinotes, frequency and notenames', 
      long_description=__doc__,
      classifiers=list(filter(None, classifiers.split('\n'))),
      author='Eduardo Moguillansky',
      author_email='eduardo.moguillansky@gmail.com',
      py_modules=['pitchtools'],
      url="https://github.com/gesellkammer/pitchtools"
)


