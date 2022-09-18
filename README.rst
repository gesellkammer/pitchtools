==========
Pitchtools
==========

*pitchtools* provides a set of functions to work with musical pitches. 

Features
--------

* convert between frequencies, midinotes and notenames
* microtones are fully supported
* split a pitch into its multiple components (pitch class, octave, microtonal deviation, etc.)
* transpose a pitch taking its spelling into consideration
* create custom pitch converters to work with custom reference frequencies, or modify the
  reference frequency globally



Documentation
=============

https://pitchtools.readthedocs.io/en/latest/


Examples
========

Convert some note names to frequencies

.. code-block:: python

    >>> from pitchtools import *
    >>> eflat_scale = "4Eb 4F 4G 4Ab 4Bb 5C 5D".split()
    >>> for note in eflat_scale:
    ...     # convert notename to frequency using the default reference frequency (442 Hz)
    ...     freq = n2f(note)
    ...     # convert frequency to midi
    ...     midinote = f2m(freq)
    ...     print(f"{note} = {freq:.1f}Hz (midi = {midinote})")
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
    cnv = PitchConverter(a4=435)
    for note in ebscale:
        # Convert to frequency with default a4=442 Hz
        freq = cnv.n2f(note)
        midinote = cnv.[Of2m(freq)
        print(f"{note} = {freq} Hz (midinote = {midinote})")


Microtones
~~~~~~~~~~

Microtones are fully supported, either as fractional midinotes or as notenames.

.. code-block:: python

    >>> from pitchtools import *
    >>> n2m("4C+")
    60.5
    >>> n2m("4Db-10")
    60.9
    >>> m2n(61.2)
    4C#+20


--------------------------------


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


-------------

Installation
============

.. code::

	pip install pitchtools
