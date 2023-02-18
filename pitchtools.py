"""

Set of routines to work with musical pitches, convert to and from frequencies,
notenames, etc. Microtones are fully supported, both as fractional midinotes and as
notenames.


Features
========

* convert between frequencies, midinotes and notenames
* microtones are fully supported
* split a pitch into its multiple components (pitch class, octave, microtonal deviation, etc.)
* transpose a pitch taking its spelling into consideration
* create custom pitch converters to work with custom reference frequencies, or modify the
  reference frequency globally


Microtonal notation
===================

Some shortcuts are used for *round* microtones:

==========  ============
 Symbol      Cents
==========  ============
 ``+``       +50
 ``-``       -50
 ``>``       +25
 ``<``       -25
==========  ============

There is some flexibility regarding notenames: **the octave can be placed
before the note or after**, and the **pitch-class is case-insensitive**.

Some example notenames
~~~~~~~~~~~~~~~~~~~~~~

==========  ============  ======================
 Midinote   Notename       Alternative notation
==========  ============  ======================
  60.25      4C+25 / 4C>    c4+25 / c>4
  60.45      4C+45          C4+45
  60.5       4C             c4
  60.75      4Db-25         Db4-25 / db4-25
  61.5       4D-            d4-
  61.80      4D-20          D4
  63         4D#            d#4
  63.5       4D#+           d#+4
  63.7       4E-30          E4-30
==========  ============  ======================


Global settings vs Converter objects
====================================


To convert to and from frequencies a reference frequency (``A4``) is needed.
In **pitchtools** there are set of global functions (:func:`m2f`, :func:`f2m`,
:func:`n2f`, etc) which rely on a global reference. This reference can be
modified via :func:`set_reference_freq`.

It is also possible to create an ad-hoc converter (:class:`PitchConverter`).
This makes it possible to customize the reference frequency without any side-effects


----------------------

Example
-------

.. code::

    # Set the value globally
    >>> set_reference_freq(443)
    >>> n2f("A4")
    443.0

    # Create a Converter object
    >>> cnv = PitchConverter(a4=435)
    >>> print(cnv.n2f("4C"))
    258.7

"""
from __future__ import annotations

import warnings
from dataclasses import dataclass as _dataclass
import math
import sys
import re as _re
import itertools as _itertools
from functools import cache as _cache
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Union
    pitch_t = Union[str, float, int]

_EPS = sys.float_info.epsilon

_flats  = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B", "C"]
_sharps = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B", "C"]

_pitchclass_chromatic = {
    'C': 0,
    'C#': 1,
    'Db': 1,
    'D': 2,
    'D#': 3,
    'Eb': 3,
    'E': 4,
    'E#': 5,
    'Fb': 4,
    'F': 5,
    'F#': 6,
    'Gb': 6,
    'G': 7,
    'G#': 8,
    'Ab': 8,
    'A': 9,
    'A#': 10,
    'Bb': 10,
    'B': 11,
    'B#': 0,
    'Cb': 11,
}

_notes2 = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

_r1 = _re.compile(r"(?P<pch>[A-Ha-h][b|#]?)(?P<oct>[-]?[\d]+)(?P<micro>[-+><↓↑][\d]*)?")
_r2 = _re.compile(r"(?P<oct>[-]?\d+)(?P<pch>[A-Ha-h][b|#]?)(?P<micro>[-+><↓↑]\d*)?")


@_dataclass
class NoteParts:
    """
    Represents the parts of a notename

    It is returned by :func:`split_notename`

    Attributes:
        octave (int): octave number, 4=central octave
        diatonic_name (str: "C", "D", "E", ... (diatonic step)
        alteration (str): the alteration as str, "#", "b", "+", "-", ">", "<"
        cents_deviation (int): number of cents deviation from the chromatic pitch

    .. seealso:: :func:`notated_pitch`
    """
    octave: int
    """octave number, 4=central octave"""

    diatonic_name: str
    """name of the diatonic step ('C', 'D', 'E', etc.)"""

    alteration: str
    """The alteration as str: '#', 'b', '+', '-', '>', '<'"""

    cents_deviation: int
    """Number of cents deviation from the chromatic pitch"""

    def __iter__(self):
        return iter((self.octave, self.diatonic_name, self.alteration, self.cents_deviation))

    @property
    def alteration_cents(self) -> int:
        """The cents corresponding to the alteration"""
        return alteration_to_cents(self.alteration)

    @property
    def diatonic_step(self) -> int:
        """The diatonic step as an index, where 0 is C"""
        return 'CDEFGABC'.index(self.diatonic_name)


@_dataclass
class _ParsedMidinote:
    """
    Represents the parts of a pitch as represented by a midinote

    Attributes:
        pitchindex (int): 0=C, 1=C#, ...
        deviation (float): in semitones, deviation from the chromatic pitch
        octave (int): 4 = central octave
        chromatic_pitch (str): the written pitch, "Eb", "F#", etc. No microtones
    """
    pitchindex: int
    deviation: float
    octave: int
    chromatic_pitch: str


_cents_repr_eighthtones = {
    0: '',
    25: '>',
    50: '+',
    -25: '<',
    -50: '-'
}

_cents_repr_quartertones = {
    0: '',
    50: '+',
    -50: '-'
}

_black_key_indexes = {1, 3, 6, 8, 10}


def cents_repr(cents:int, eighthToneShortcuts=True) -> str:
    """
    Return the string representation of cents

    ======   =======================
    cents     string representation
    ======   =======================
    0          ''
    15         +15
    25         > (if ``eighthToneShortcuts == True``)
    45         +45
    50         +
    60         +60
    -15        -15
    -25        < (if ``eighthToneShortcuts == True``)

    ======   =======================

    .. seealso:: :func:`construct_notename`
    """
    if eighthToneShortcuts:
        shortcut = _cents_repr_eighthtones.get(cents)
    else:
        shortcut = _cents_repr_quartertones.get(cents)
    if shortcut:
        return shortcut
    else:
        return f'+{cents}' if cents > 0 else str(cents)


@_dataclass
class NotatedPitch:
    """
    A parsed notename to be queried in relation to its musical notation

    It is returned by :func:`notated_pitch`

    Attributes:
        octave: the octave (4=central octave)
        diatonic_index: The index of the pitch class without accidentals, 0=C, 1=D, 2=E, ...
        diatonic_name: The name corresponding to the diatonic_index: "C", "D", "E", ...
        chromatic_index: The index of the chormatic pitch class: 0=C, 1=C#/Db, 2=D, ...
        chromatic_name: The name corresponding to the chromatic_index "C", "Db", ...
        diatonic_alteration: the alteration in relation to the diatonic pitch. For C# this would be 1.0, for Db this would be -1.0
        chromatic_alteration: for C#+50 this would be 0.5
        accidental_name: the name of the accidental used ('natural', 'natural-up','quarter-sharp', etc.)

    Example
    ~~~~~~~

        >>> notated_pitch("4C#+15")
        NotatedPitch(octave=4, diatonic_index=0, diatonic_name='C', chromatic_index=1,
                     chromatic_name='C#', diatonic_alteration=1.15, chromatic_alteration=0.15,
                     accidental_name='sharp-up')
        >>> notated_pitch("4Db+15")
        NotatedPitch(octave=4, diatonic_index=1, diatonic_name='D', chromatic_index=1,
                     chromatic_name='Db', diatonic_alteration=-0.85, chromatic_alteration=0.15,
                     accidental_name='flat-up')

    """
    octave: int
    diatonic_index: int
    diatonic_name: str
    chromatic_index: int
    chromatic_name: str
    diatonic_alteration: float
    chromatic_alteration: float
    accidental_name: str

    @property
    def fullname(self) -> str:
        "The full name of this notated pitch"
        return f"{self.octave}{self.chromatic_name}{self.cents_str}"

    @property
    def vertical_position(self) -> int:
        """
        Abstract value indicating the vertical notated position 
        """
        return self.octave * 7 + self.diatonic_index

    @property
    def midinote(self) -> float:
        "The midinote corresponding to this notated pitch"
        return (self.octave+1)*12 + self.chromatic_index + self.chromatic_alteration

    def microtone_index(self, semitone_divisions=2) -> int:
        """The index of the nearest microtone

        For example, if semitone_divisions is 2, then

        ====   ================
        note   microtone index
        ====   ================
        4C     0
        5C     0
        4C+    1
        4C#    2
        4Db    2
        …      …
        ====   ================
        """
        m = self.midinote
        quantized = round(m*semitone_divisions)/semitone_divisions
        idx = quantized%12
        return int(idx*semitone_divisions)

    @property
    def is_white_key(self) -> bool:
        "Is this a white key?"
        return self.chromatic_index not in _black_key_indexes

    @property
    def is_black_key(self) -> bool:
        """Is this a black key?"""
        return self.chromatic_index in _black_key_indexes

    @property
    def cents_deviation(self) -> int:
        """The cents deviation from the notated chromatic pitch"""
        return int(self.chromatic_alteration * 100)

    @property
    def cents_sign(self) -> str:
        "The sign of the cents deviation ('', '+', '-')"
        if self.chromatic_alteration == 0:
            return ''
        elif self.chromatic_alteration > 0:
            return '+'
        else:
            return '-'

    @property
    def cents_str(self) -> str:
        "The cents deviation as a string"
        cents = self.cents_deviation
        if cents == 0:
            return ''
        elif cents == 50:
            return '+'
        elif cents == -50:
            return '-'
        elif cents > 0:
            return f'+{cents}'
        else:
            return str(cents)

    def alteration_direction(self, min_alteration=0.5):
        """
        Returns the direction of the alteration

        (the table assumes min_alteration==0.5)

        ===== ====================
        Note  Alteration Direction
        ===== ====================
        4C     0
        4C#    1
        4Eb   -1
        4C+    1
        4F-25  0
        4Bb    -1
        4A+25  0
        ===== ====================

        """
        if self.diatonic_alteration >= min_alteration:
            return 1
        elif self.diatonic_alteration <= -min_alteration:
            return -1
        return 0


class PitchConverter:
    """
    Convert between midinote, frequency and notename.

    Args:
        a4: the reference frequency
        eightnote_symbol: if True, a special symbol is used
            (">", "<") when a note is exactly 25 cents higher
            or lower (for example, "4C>"). Otherwise, a notename
            would be, for example, "4C+25"

    Example
    ~~~~~~~

        >>> cnv = PitchConverter(a4=435)
        >>> cnv.m2f(69)
        435.0
        >>> cnv.f2n(440)
        '4A+20'
    """

    def __init__(self, a4=442.0, eightnote_symbol=True):
        self.a4 = a4
        self.eighthnote_symbol = eightnote_symbol

    def set_reference_freq(self, a4:float) -> None:
        """
        Set the reference freq. (the freq. of A4) for this converter

        Args:
            a4: the freq. of A4 in Hz

        .. seealso:: :func:`get_reference_frequency`, :meth:`PitchConverter.get_reference_freq`
        """
        self.a4 = a4

    def get_reference_freq(self) -> float:
        """
        Get the reference frequency for this converter

        Returns:
            the freq. of A4

        .. seealso:: :func:`set_reference_frequency`, :meth:`~PitchConverter.set_reference_freq`

        """
        return self.a4

    def f2m(self, freq: float) -> float:
        """
        Convert a frequency in Hz to a midi-note

        Args:
            freq: the frequency to convert, in Hz

        Returns:
            the midi note corresponding to freq

        .. seealso:: :meth:`~PitchConverter.set_reference_freq`
        """
        if freq<9:
            return 0
        return 12.0*math.log(freq/self.a4, 2)+69.0

    def freq_round(self, freq: float, semitone_divisions=1) -> float:
        """
        Round the freq. to the nearest semitone or fraction thereof

        Args:
            freq: the freq. to round
            semitone_divisions: the number of divisions per semitone

        Returns:
            the rounded frequency

        .. seealso::  :func:`pitch_round`, :func:`quantize_notename`
        """
        return self.m2f(round(self.f2m(freq) * semitone_divisions) / semitone_divisions)

    def m2f(self, midinote: float) -> float:
        """
        Convert a midi-note to a frequency

        Args:
            midinote: the midinote to convert to frequency

        Returns:
            the freq. corresponding to midinote

        .. seealso:: :func:`set_reference_freq`
        """
        return 2**((midinote-69)/12.0)*self.a4

    def m2n(self, midinote: float) -> str:
        """
        Convert midinote to notename

        Args:
            midinote: a midinote (60=C4)

        Returns:
            the notename corresponding to midinote.

        .. seealso:: :func:`n2m`, :func:`construct_notename`, :func:`notated_pitch`

        """
        octave, chromatic_name, alteration, cents = self.midi_to_note_parts(midinote)
        if cents == 0:
            return str(octave)+chromatic_name+alteration
        if cents > 0:
            if cents < 10:
                return f"{octave}{chromatic_name}{alteration}+0{cents}"
            return f"{octave}{chromatic_name}{alteration}+{cents}"
        else:
            if -10 < cents:
                return f"{octave}{chromatic_name}{alteration }-0{abs(cents)}"
            return f"{octave}{chromatic_name}{alteration }{cents}"

    def n2m(self, note: str) -> float:
        """ 
        Convert a notename to a midinote 

        Args:
            note: the notename

        Returns:
            the midinote corresponding to note

        .. seealso:: :func:`m2n`
        """
        return n2m(note)

    def n2f(self, note: str) -> float:
        """ Convert a notename to its corresponding frequency """
        return self.m2f(n2m(note))

    def f2n(self, freq: float) -> str:
        """ 
        Return the notename corresponding to the given freq 

        Args:
            freq: the freq. to convert

        Returns:
            the corresponding notename
        """
        return self.m2n(self.f2m(freq))

    def pianofreqs(self, start="A0", stop="C8") -> list[float]:
        """
        Generate an array of the frequencies for all the piano keys

        Args:
            start: the starting note
            stop: the ending note

        Returns:
            a list of frequencies
        """
        m0 = int(n2m(start))
        m1 = int(n2m(stop))
        midinotes = range(m0, m1+1)
        freqs = [self.m2f(m) for m in midinotes]
        return freqs

    def asmidi(self, x:int|float|str) -> float:
        """ 
        Convert x to a midinote 

        Args:
            x: an object which can be converted to a midinote (a freq., a notename)

        Returns:
            The corresponding midinote.

        Example
        -------

        .. code::

            >>> from pitchtools import *
            >>> cnv = PitchConverter()
            >>> cnv.asmidi("4C+10Hz")
            272.8

        """
        if isinstance(x, str):
            return self.str2midi(x)
        else:
            return x

    def str2midi(self, s: str) -> float:
        """
        Accepts all that n2m accepts but with the addition of frequencies

        .. note:: The hz part must be at the end

        Args:
            s: pitch describes as a string. Possible values: "100hz", "4F+20hz", "8C-4hz"

        Returns:
            the corresponding midinote

        """
        ending = s[-2:]
        if ending != "hz" and ending != "Hz":
            return self.n2m(s)
        srev = s[::-1]
        minusidx = srev.find("-")
        plusidx = srev.find("+")
        if minusidx<0 and plusidx<0:
            return self.f2m(float(s[:-2]))
        if minusidx>0 and plusidx>0:
            if minusidx<plusidx:
                freq = -float(s[-minusidx:-2])
                notename = s[:-minusidx-1]
            else:
                freq = float(s[-plusidx:-2])
                notename = s[:-plusidx-1]
        elif minusidx>0:
            freq = -float(s[-minusidx:-2])
            notename = s[:-minusidx-1]
        else:
            freq = float(s[-plusidx:-2])
            notename = s[:-plusidx-1]
        return self.f2m(self.n2f(notename)+freq)

    def midi_to_note_parts(self, midinote: float) -> tuple[int, str, str, int]:
        """
        Convert a midinote into its parts as a note

        Args:
            midinote: the midinote to analyze

        Returns:
            a tuple (``octave``: *int*, ``chromatic_note``: *str*, ``microtonal_alternation``: *str*, ``cents_deviation``: *int*),
            where ``octave`` is the octave number; ``chromatic_note`` is the pitch class


        Example
        ~~~~~~~

            >>> import pitchtools as pt
            >>> pt.midi_to_note_parts(60.5)
            (4, 'C', '+', 0)
            >>> pt.midi_to_note_parts(61.2)
            (4, 'C#', '', 20)

        """
        i = int(midinote)
        micro = midinote-i
        octave = int(midinote/12.0)-1
        ps = int(midinote%12)
        cents = int(micro*100+0.5)
        if cents == 0:
            return (octave, _sharps[ps], "", 0)
        elif cents == 50:
            if ps in {1, 3, 6, 8, 10}:
                return (octave, _sharps[ps+1], "-", 0)
            return (octave, _sharps[ps], "+", 0)
        elif cents == 25 and self.eighthnote_symbol:
            if ps in (6, 10,):
                return (octave, _flats[ps], ">", 0)
            return (octave, _sharps[ps], ">", 0)
        elif cents == 75 and self.eighthnote_symbol:
            ps += 1
            if ps>11:
                octave += 1
            if ps in {1, 3, 6, 8, 10}:
                return (octave, _flats[ps], "<", 0)
            else:
                return (octave, _sharps[ps], "<", 0)
        elif cents>50:
            cents = 100-cents
            ps += 1
            if ps>11:
                octave += 1
            return (octave, _flats[ps], "", -cents)
        else:
            return (octave, _sharps[ps], "", cents)

    def normalize_notename(self, notename: str) -> str:
        """ 
        Convert notename to its canonical form

        The canonical form follows the scheme ``octave:pitchclass:microtone``

        Args:
            notename: the note to normalize

        Returns:
            the normalized notename

        Example
        -------

        .. code::

            >>> normalize_notename("a4+24")
            4A+24

        """
        return self.m2n(self.n2m(notename))

    def as_midinotes(self, x) -> list[float]:
        """
        Tries to interpret `x` as a list of pitches, returns these as midinotes

        Args:
            x: either list of midinotes (floats/ints), a list of notenames (str), one
                str with notenames (divided by spaces), or a single notename or midinote

        Returns:
            the corresponding list of midinotes.

        Example
        ~~~~~~~

            >>> as_midinotes(["4G", "4C"])
            [67., 60.]
            >>> as_midinotes((67, 60))
            [67., 60.]
            >>> as_midinotes("4G 4C 4C+10hz")
            [67., 60., 60.65]

        """
        if isinstance(x, str):
            notenames = x.split()
            return [self.str2midi(n) for n in notenames]
        elif isinstance(x, (list, tuple)):
            midinotes = []
            for n in x:
                if isinstance(n, str):
                    midinotes.append(self.str2midi(n))
                elif isinstance(n, (int, float)):
                    midinotes.append(n)
                else:
                    raise TypeError(f"Expected a str, an int or a float, got {n}")
            return midinotes
        elif isinstance(x, (float, int)):
            return [x]
        else:
            raise TypeError(f"Expected a str, list of str or list of float, got {x}")


@_cache
def n2m(note: str) -> float:
    """
    Convert a notename to a midinote

    Args:
        note: the notename

    Returns:
        the corresponding midi note

    Two formats are supported:

    * 1st format (pitchclass first): ``C#2``, ``D4``, ``Db4+20``, ``C4>``, ``Eb5<``
    * 2nd format (octave first): ``2C#``, ``4D+``, ``7Eb-14``

    .. note::

        The second format, with its clear hierarchy ``octave:pitch:microtone`` is
        the canonical one and used when converting a midinote to a notename


    ========      ========
    Input         Output
    ========      ========
    4C            60
    4D-20         61.8
    4Eb+          63.5
    4E<           63.75
    4C#-12        60.88
    ========      ========

    Microtonal alterations
    ~~~~~~~~~~~~~~~~~~~~~~

    ==========    ========
    Alteration    Cents
    ==========    ========
    ``+``          +50
    ``-``          -50
    ``>``          +25
    ``<``          -25
    ==========    ========

    .. seealso:: :func:`str2midi`
    """
    if not isinstance(note, str):
        raise TypeError(f"expected a str, got {note} of type {type(note)}")

    if note[0].isalpha():
        m = _r1.search(note)
    else:
        m = _r2.search(note)
    if not m:
        raise ValueError("Could not parse note " + note)
    groups = m.groupdict()
    pitchstr = groups["pch"]
    octavestr = groups["oct"]
    microstr = groups["micro"]

    pc = _notes2[pitchstr[0].lower()]

    if len(pitchstr) == 2:
        alt = pitchstr[1]
        if alt == "#":
            pc += 1
        elif alt == "b":
            pc -= 1
        else:
            raise ValueError("Could not parse alteration in " + note)
    octave = int(octavestr)
    if not microstr:
        micro = 0.0
    elif microstr == "+":
        micro = 0.5
    elif microstr == "-":
        micro = -0.5
    elif microstr == ">" or microstr == "↑":
        micro = 0.25
    elif microstr == "<" or microstr == "↓":
        micro = -0.25
    else:
        micro = int(microstr) / 100.0

    if pc > 11:
        pc = 0
        octave += 1
    elif pc < 0:
        pc = 12 + pc
        octave -= 1
    return (octave + 1) * 12 + pc + micro


def is_valid_notename(notename: str, minpitch=12) -> bool:
    """
    Returns true if *notename* is valid

    Args:
        notename: the notename to check
        minpitch: a min. midi note

    Returns:
        True if this is a valid notename

    .. seealso:: :func:`split_notename`
    """
    try:
        midi = n2m(notename)
        return midi >= minpitch
    except ValueError:
        return False


def _pitchname(pitchidx: int, micro: float) -> str:
    """
    Given a pitchindex (0-11) and a microtonal alteracion (between -0.5 and +0.5),
    return the pitchname which better represents pitchindex

    0, 0.4      -> C
    1, -0.2     -> Db
    3, 0.4      -> D#
    3, -0.2     -> Eb
    """
    blacknotes = {1, 3, 6, 8, 10}
    if micro < 0:
        if pitchidx in blacknotes:
            return _flats[pitchidx]
        else:
            return _sharps[pitchidx]
    elif micro == 0:
        return _sharps[pitchidx]
    else:
        if pitchidx in blacknotes:
            return _sharps[pitchidx]
        return _flats[pitchidx]


def _parse_midinote(midinote: float) -> _ParsedMidinote:
    """
    Convert a midinote into its pitch components

    Args:
        midinote: the midinote, where 60 corresponds to central C (C4)

    Returns:
        a ParsedMidinote, which is a NamedTuple with fields pitchindex (int), 
        deviation (in semitones, float), octave (int) and chromaticPitch (str)

    ======    =========
    Input     Output
    ======    =========
    63.2      (3, 0.2, 4, "D#")
    62.8      (3, -0.2, 4, "Eb")
    ======    =========
    """
    i = int(midinote)
    micro = midinote - i
    octave = int(midinote / 12.0) - 1
    ps = int(midinote % 12)
    cents = int(micro * 100 + 0.5)
    if cents == 50:
        if ps in (1, 3, 6, 8, 10):
            ps += 1
            micro = -0.5
        else:
            micro = 0.5
    elif cents > 50:
        micro = micro - 1.0
        ps += 1
        if ps == 12:
            octave += 1
            ps = 0
    pitchname = _pitchname(ps, micro)
    return _ParsedMidinote(ps, round(micro, 2), octave, pitchname)


def ratio2interval(ratio: float) -> float:
    """
    Convert the ratio between 2 freqs. to their interval in semitones
    
    Args:
        ratio: a ratio between two frequencies

    Returns:
        The interval (in semitones) between those frequencies

    Example
    =======
    
    .. code::
    
        >>> f1 = n2f("C4")
        >>> f2 = n2f("D4")
        >>> ratio2interval(f2/f1)   
        2

    .. seealso:: :func:`interval2ratio`, :func:`r2i`, :func:`i2r`
    """
    return 12 * math.log(ratio, 2)


def interval2ratio(interval: float) -> float:
    """
    Convert a semitone interval to a ratio between 2 freqs.

    Args:
        interval: an interval in semitones

    Returns:
        the ratio between frequencies corresponding to the given interval


    Example
    =======

    .. code::

        >>> f1 = n2f("C4")
        >>> r = interval2ratio(7)  # a 5th higher
        >>> f2n(f1*r)  
        4G

    .. seealso:: :func:`ratio2interval`, :func:`r2i`, :func:`i2r`
    """
    return 2 ** (interval / 12.0)


r2i = ratio2interval
i2r = interval2ratio


def quantize_midinote(midinote: float, divisions_per_semitone, method="round"
                      ) -> float:
    """
    Quantize midinote to the next semitone division

    Args:
        midinote: the midinote to round
        divisions_per_semitone: resolution of the pitch grid (1, 2 or 4)
        method: "round" to quantize to the nearest value in grid, "floor" to
            take the next lesser value

    Returns:
        the quantized midinote

    .. seealso:: :func:`quantize_notename`, :func:`pitch_round`, :func:`freq_round`

    """
    if method == "round":
        return round(midinote * divisions_per_semitone) / divisions_per_semitone
    elif method == "floor":
        return int(midinote * divisions_per_semitone) / divisions_per_semitone
    raise ValueError(f"method should be either 'round' or 'floor', got {method}")


def quantize_notename(notename: str, divisions_per_semitone) -> str:
    """
    Quantize notename to the next semitone divisions

    Args:
        notename: the notename to quantize
        divisions_per_semitone: the number of divisions of the semitone 
            (1 to quantize to nearest chromatic note)

    Returns:
        the notename of the quantized pitch

    Example
    -------

    .. code::

        >>> quantize_notename("4A+18", 4)
        4A+25


    .. seealso:: :func:`quantize_midinote`
    """
    octave, letter, alter, cents = split_notename(notename)
    cents = int(round(cents/100 * divisions_per_semitone) / divisions_per_semitone * 100)
    if cents >= 100 or cents <= -100:
        notename = m2n(round(n2m(notename) * divisions_per_semitone) / divisions_per_semitone)
        octave, letter, alter, cents = split_notename(notename)
    return construct_notename(octave, letter, alter, cents)


def construct_notename(octave:int, letter:str, alter:Union[int, str], cents:int,
                       normalize=False) -> str:
    """
    Utility function to construct a valid notename

    Args:
        octave: the octave of the notename (4 = central octave)
        letter: the pitch letter, one of "a", "b", "c", ... (case is not important)
        alter: 1 for sharp, -1 for flat, 0 for natural. An alteration as str is also
            possible. `alter` should not be microtonal, any microtonal
            deviation must be set via the `cents` param)
        cents: cents deviation from chromatic pitch
        normalize: if True, normalize/check the resulting notename (see
        `normalize_notename`)

    Returns:
        the notename

    =======  =======  ======  ======  ==================
    octave   letter   alter   cents   notename
    =======  =======  ======  ======  ==================
    4        a        -1      -25     4Ab-25
    6        d        #       +40     6D#+40
    5        e        0       -50     5E-
    =======  =======  ======  ======  ==================

    .. seealso:: :func:`split_notename`
    """
    if isinstance(alter, str):
        alterstr = alter
    else:
        alterstr = "#" if alter == 1 else "b" if alter == -1 else ""
    if cents == 50:
        centsstr = "+"
    elif cents == -50:
        centsstr = "-"
    else:
        centsstr = "+" + str(cents) if cents > 0 else str(cents) if cents < 0 else ""
    notename = f"{octave}{letter.upper()}{alterstr}{centsstr}"
    if normalize:
        notename = normalize_notename(notename)
    return notename


def pitchbend2cents(pitchbend: int, maxcents=200) -> int:
    """
    Convert a MIDI pitchbend to its corresponding deviation in cents

    Args:
        pitchbend: the MIDI pitchbend value, between 0-16383 (8192 = 0 semitones)
        maxcents: the cents corresponding to the max. bend

    Returns:
        the bend expressed in cents

    .. seealso:: :func:`cents2pitchbend`
    """
    return int(((pitchbend / 16383.0) * (maxcents * 2.0)) - maxcents + 0.5)


def cents2pitchbend(cents: int, maxcents=200) -> int:
    """
    Convert a deviation in cents to the corresponding value as pitchbend.

    Args:
        cents: the bend interval, in cents
        maxcents: the cents corresponding to the max. bend

    Returns:
        the bend MIDI value (between 0-16383)

    .. seealso:: :func:`pitchbend2cents`
    """
    return int((cents + maxcents) / (maxcents * 2.0) * 16383.0 + 0.5)


_centsrepr = {
    '#+': 150,
    '#>': 125,
    '#':  100,
    '#<': 75,
    '+':  50,
    '>':  25,
    '':   0,
    '<':  -25,
    '-':  -50,
    'b>': -75,
    'b':  -100,
    'b<': -125,
    'b-': -150
}


def alteration_to_cents(alteration: str) -> int:
    """
    Convert an alteration to its corresponding cents deviation

    Args:
        alteration: the alteration as str (see table below)

    Returns:
        the alteration in cents

    =============  =======
     Alternation    Cents
    =============  =======
        #+          150
        #>          125
        #           100
        #<          75
        \+          50
        >           25
        <           -25
        \-          -50
        b>          -75
        b           -100
        b<          -125
        b-          -150
    =============  =======
    

    """
    cents = _centsrepr.get(alteration)
    if cents is None:
        raise ValueError(f"Unknown alteration: {alteration}, "
                         f"it should be one of {', '.join(_centsrepr.keys())}")
    return cents


def _asint(x):
    try:
        return int(x)
    except ValueError:
        return None


def _parse_centstr(centstr: str) -> int:
    if not centstr:
        return 0
    cents = _centsrepr.get(centstr)
    if cents is None:
        cents = _asint(centstr)
    return cents


@_cache
def split_notename(notename: str, default_octave=-1) -> NoteParts:
    """
    Splits a notename into octave, letter, alteration and cents

    Args:
        notename: the notename to split
        default_octave: if an octave-less pitch is given (e.g. 4C#-7) this
            value is returned as the octave. It can then be used to query if the notename
            had an octave or not. In the default we avoid using 0 since this is a valid
            octave

    Microtonal alterations, like "+" (+50), "-" (-50), ">" (+25), "<" (-25)
    are resolved into cents alterations

    =======    ===================
     Input           Output
    =======    ===================
    4C#+10     4, "C", "#", 10
    Eb4-15     4, "E", "b", -15
    4C+        4, "C", "", 50
    5Db<       5, "D", "b", -25
    =======    ===================

    .. seealso:: :func:`notated_pitch`, :func:`construct_notename`
    """
    if not notename[0].isdecimal():
        # C#4-10
        cursor = 1
        letter = notename[0]
        # find alteration
        l1 = notename[1]
        if l1 == "#":
            alter = "#"
            cursor = 2
        elif l1 == "b":
            alter = "b"
            cursor = 2
        else:
            alter = ""
            cursor = 1

        octchar = notename[cursor]
        if octchar.isdecimal():
            octave = int(octchar)
            cursor += 1
        else:
            octave = default_octave

        centstr = notename[cursor:]
        cents = _parse_centstr(centstr)
        if cents is None:
            raise ValueError(f"Could not parse cents '{centstr}' while parsing note '{notename}'")
    else:
        # 4C#-10
        octave = int(notename[0])
        letter = notename[1]
        rest = notename[2:]
        cents = 0
        alter = ""
        if rest:
            r0 = rest[0]
            if r0 == "b":
                alter = "b"
                centstr = rest[1:]
            elif r0 == "#":
                alter = "#"
                centstr = rest[1:]
            else:
                centstr = rest
            cents = _parse_centstr(centstr)
            if cents is None:
                raise ValueError(f"Could not parse cents '{centstr}' while parsing note '{notename}'")
    return NoteParts(octave, letter.upper(), alter, cents)


def split_cents(notename: str) -> tuple[str, int]:
    """
    Split a notename into the chromatic note and the cents deviation.

    The cents deviation can be a negative or possitive integer

    Args:
        notename: the notename to split

    Returns:
        the chromatic pitch and the cents deviation from this chromatic pitch


    ========   ============
    Input      Output
    ========   ============
    "4E-"      ("4E", -50)
    "5C#+10"   ("5C#", 10)
    ========   ============

    .. seealso:: :func:`split_notename`
    """
    parts = split_notename(notename)
    return f"{parts.octave}{parts.diatonic_name}{parts.alteration}", parts.cents_deviation
    

def enharmonic(notename: str) -> str:
    """
    Returns the enharmonic variant of notename

    For simplicity we considere a possible enharmonic variant a note
    with the same sounding pitch and an alteration smaller than 150
    cents from the note without any alteration (no double sharps or
    flats). Also not accepted are enharmonics like Fb or E#

    Args:
        notename (str): the note to find an enharmonic variant to

    Returns:
        either the enharmonic variant or the note itself

    =====  ===========  ================
    Note   Enharmonic   Has Enharmonic?
    =====  ===========  ================
    4#     4Db           ✓
    4C+    4Db-          ✓
    4E     4E            –
    4E#    4F            ✓
    4A+10  4A+10         –
    4E-25  4E-25         –
    4E-    4D#+          ✓
    =====  ===========  ================

    .. seealso:: :func:`transpose`
    """
    p = notated_pitch(notename)
    if abs(p.diatonic_alteration) < 1:
        if abs(p.cents_deviation) < 50:
            return notename
        if p.cents_deviation >= 50:
            chrom = _flats[p.chromatic_index+1]
            octave = p.octave if p.chromatic_name != "B" else p.octave+1
            return f"{octave}{chrom}{cents_repr(p.cents_deviation-100)}"
        else:
            # 4E- : 4D#+
            # 4E-60 : 4D#+40
            chrom = _sharps[(p.chromatic_index-1)%12]
            octave = p.octave if p.chromatic_name != "C" else p.octave-1
            return f"{octave}{chrom}{cents_repr(100+p.cents_deviation)}"
    if p.diatonic_alteration >= 1:
        # 4C# : 4Db
        # 4C#+25 : 4Db+25
        # 4C#+ : 4D-
        # 4C#+60 : 4D-40
        # 4D#-25 : 4Eb-25
        # 4D#-70 : 4D+30
        if 0 <= abs(p.cents_deviation) < 50:
            chrom = _flats[p.chromatic_index]
            return f"{p.octave}{chrom}{p.cents_str}"
        elif 50 <= p.cents_deviation < 100:
            chrom = _flats[p.chromatic_index+1]
            centstr = cents_repr(p.cents_deviation-100)
        elif -100 < p.cents_deviation < 50:
            chrom = _flats[(p.chromatic_index-1)%12]
            centstr= cents_repr(100+p.cents_deviation)
        else:
            raise ValueError(f"Invalid cents deviation {p.cents_deviation} ({notename=}, {p=})")
        return f"{p.octave}{chrom}{centstr}"
    else: #  p.diatonic_alteration == -1:
        # 4Db : 4C#
        # 4Db-25 : 4C#-25
        # 4Db-   : 4C+
        # 4Db-60 : 4C+40
        # 4Eb+25 : 4D#+25
        # 4Eb+70 : 4E-30
        if 0 <= abs(p.cents_deviation) < 50:
            chrom = _sharps[p.chromatic_index]
            return f"{p.octave}{chrom}{p.cents_str}"
        elif 50 <= p.cents_deviation < 100:
            chrom = _sharps[p.chromatic_index-1]
            centstr = cents_repr(p.cents_deviation-100)
        elif -100 < p.cents_deviation:
            chrom = _sharps[p.chromatic_index-1]
            centstr = cents_repr(100+p.cents_deviation)
        else:
            raise ValueError(f"Invalid cents deviation {p.cents_deviation} ({notename=}, {p=})")
        return f"{p.octave}{chrom}{centstr}"


def pitch_round(midinote: float, semitone_divisions=1) -> tuple[str, int]:
    """
    Round midinote to the next (possibly microtonal) note

    Returns the rounded notename and the cents deviation
    from the original pitch to the nearest semitone

    Args:
        midinote: the midinote to round, as float
        semitone_divisions: the number of division per semitone

    Returns:
        a tuple (rounded note, cents deviation). NB: the cents deviation can
        be negative (see example below)

    Example
    =======

    .. code::
        
        >>> pitch_round(60.1)
        ("4C", 10)
        >>> pitch_round(60.75)
        ("4D<", -25)

    .. seealso:: :func:`quantize_midinote`
    """
    rounding_factor = 1 / semitone_divisions
    rounded_midinote = round(midinote/rounding_factor)*rounding_factor
    notename = m2n(rounded_midinote)
    basename, cents = split_cents(notename)
    mididev = midinote-n2m(basename)
    centsdev = int(round(mididev*100))
    return notename, centsdev


def notated_interval(n0: str, n1: str) -> tuple[int, float]:
    """
    Gives information regarding the notated interval between n0 and n1

    Args:
        n0: the first notename
        n1: the second notename

    Return:
        a tuple (delta vertical position, delta midinote).

    Examples
    ~~~~~~~~

    >>> notated_interval("4C", "4D")
    (1, 2)        # 1 vertical step, 2 semitone steps
    >>> notated_interval("4C", "4C+")
    (0, 0.5)
    >>> notated_interval("4C", "4Db")
    (1, 1)
    >>> notated_interval("4Db", "4C")
    (-1, -1)

    .. seealso:: :func:`notated_pitch`
    """
    vertpos0 = vertical_position(n0)
    vertpos1 = vertical_position(n1)
    return (vertpos1-vertpos0, n2m(n1)-n2m(n0))


def enharmonic_variations(notes: list[str],
                          fixedslots: dict[int, int|None] = None,
                          force=False
                          ) -> list[tuple[str]]:
    """
    Generates all enharmonic variations of the given notes

    Args:
        notes: a list of notenames
        fixedslots: a dict of slot:alteration_direction, fixes the given slots
            to a given alteration direction (1=#, -1=b). If Slot 0 corresponds to C,
            1 to C+/Db-, 2 to C#/Db, etc.
        force: if True, it will always return at least a variation even if there are
            no valid solutions

    Returns:
        a list of enharmonic alternatives

    .. seealso:: :func:`enharmonic`

    """
    # C C+ C# D- D D+ D# E- E E+ F F+ F# G- G G+ G# A- A A+ A# B- B B+
    # 0 1  2  3  4 5  6  7  8 9  0 1  2  3  4 5  6  7  8 9  0  1  2 3
    non_enharmonic_slots = {0, 4, 8, 10, 14, 18, 22}
    variants_per_note = [(n, enharmonic(n)) for n in notes]
    allvariants: list[tuple[str]] = []
    if fixedslots is None:
        fixedslots = {}
    for indexes in _itertools.product(*[(0, 1)] * len(notes)):
        # indexes contains a row of the form (0, 0, 1) for 3 notes
        row: list[str] = []
        rowslots = fixedslots.copy()
        for idx, variants in zip(indexes, variants_per_note):
            notename = variants[idx]
            notated = notated_pitch(notename)
            slotindex = notated.microtone_index(semitone_divisions=2)
            if slotindex in non_enharmonic_slots:
                row.append(notename)
                continue
            fixed_dir = rowslots.get(slotindex)
            if fixed_dir is None or fixed_dir == 0 or fixed_dir == notated.alteration_direction():
                rowslots[slotindex] = notated.alteration_direction()
                row.append(notename)
            else:
                # the slot has an opposite direction, for example one note
                # was spelled C#, so we can't accept Db as alteration
                break
        if len(row) == len(notes):
            # a valid row
            allvariants.append(tuple(row))
    out = list(set(allvariants))
    return out if out or not force else [tuple(notes)]


_chromatic_transpositions = {
    'C': ('C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B', 'C'),
    'C#': ('C#', 'D', 'D#', 'E', 'E#', 'F#', 'G', 'G#', 'A', 'A#', 'B', 'C', 'C#'),
    'Db': ('Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B', 'C', 'Db'),
    'D': ('D', 'Eb', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B', 'C', 'C#', 'D'),
    'D#': ('D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B', 'C', 'C#', 'D', 'D#'),
    'Eb': ('Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B', 'C', 'Db', 'D', 'Eb'),
    'E': ('E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B', 'C', 'C#', 'D', 'D#', 'E'),
    'F': ('F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B', 'C', 'Db', 'D', 'Eb', 'E', 'F'),
    'F#': ('F#', 'G', 'G#', 'A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#'),
    'Gb': ('Gb', 'G', 'Ab', 'A', 'Bb', 'B', 'C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb'),
    'G': ('G', 'Ab', 'A', 'Bb', 'B', 'C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G'),
    'G#': ('G#', 'A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#'),
    'Ab': ('Ab', 'A', 'Bb', 'B', 'C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab'),
    'A': ('A', 'Bb', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A'),
    'A#': ('A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#'),
    'Bb': ('Bb', 'B', 'C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb'),
    'B': ('B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
}


_chromatic_interval_to_diatonic_interval = {
    0: 0,
    1: 1,
    2: 1,
    3: 2,
    4: 2,
    5: 3,
    6: 3,
    7: 4,
    8: 5,
    9: 5,
    10: 6,
    11: 6,
    12: 7
}


def transpose(notename: str, interval: float, white_enharmonic=True) -> str:
    """
    Transpose a note by an interval taking spelling into account

    The main difference with just doing ``m2n(n2m(notename)+interval)`` is that
    here the spelling of the note is taken into consideration when transposing.
    Notice that as the interval is given as a float there is no means to convey
    enharmonic intervals, like augmented second, etc.

    ========= ========= ===============================  ===========================
    notename  interval  transpose                        ``m2n(n2m(name)+interval)``
    ========= ========= ===============================  ===========================
     4Eb      5         4Ab                              4G#
     4D#      5         4G#                              4G#
     4Db      2         4Eb                              4D#
     4C#      2         4D#                              4D#
     4Db      4.2       4F+20                            4F+20
     4C#      4.2       4E#+20 (white_enharmonic=True)   4F+20
    ========= ========= ===============================  ===========================

    Args:
        notename: the note
        interval: an interval in semitones
        white_enharmonic: if True, allow pitches like 4E# or 5Cb or any
            microtonal variation (4E#+20). If False, such pitches are
            replaced by their enharmonic (4F, 4B).

    Returns:
        the transposed pitch

    .. seealso:: :func:`enharmonic`

    """
    midi1 = n2m(notename)
    midi2 = midi1 + interval
    octave = split_notename(m2n(midi2)).octave
    parts1 = split_notename(notename)
    chromatic1 = parts1.diatonic_name + parts1.alteration
    rounded_interval = round(interval)
    deviation = interval - rounded_interval
    deviationcents = round(deviation * 100) + parts1.cents_deviation
    chromatic2 = _chromatic_transpositions.get(chromatic1)[rounded_interval % 12]
    diff = n2m(f"{octave}{chromatic2}") - n2m(notename)
    if diff < 0 and interval > 0:
        octave += 1
    elif diff > 0 and interval < 0:
        octave -= 1

    letter = chromatic2[0]
    alter = chromatic2[1] if len(chromatic2) == 2 else 0

    if not white_enharmonic:
        if letter == 'E' and alter == '#':
            letter, alter = 'F', ''
        elif letter == 'F' and alter == 'b':
            letter, alter = 'E', ''
        elif letter == 'B' and alter == '#':
            letter, alter = 'C', ''
            octave += 1
        elif letter == 'C' and alter == 'b':
            letter, alter = 'B', ''
            octave -= 1

    out = construct_notename(octave=octave, letter=letter, alter=alter, cents=deviationcents)
    if deviationcents < -50 or deviationcents > 50:
        out = normalize_notename(out)
    return out


def freq2mel(freq: float) -> float:
    """
    Convert a frequency to its place in the mel-scale

    .. note::
        The mel scale is a perceptual scale of pitches judged by listeners to be
        equal in distance from one another

    .. seealso:: :func:`mel2freq`
    """
    return 1127.01048 * math.log(1. + freq/700)


def mel2freq(mel: float) -> float:
    """
    Convert a position in the mel-scale to its corresponding frequency

    Args:
        mel: the mel index (can be fractional)

    Returns:
        the corresponding freq. in Hz


    .. note::
        The mel scale is a perceptual scale of pitches judged by listeners to be
        equal in distance from one another

    .. seealso:: :func:`freq2mel`
    """
    return 700. * (math.exp(mel / 1127.01048) - 1.0)


_centsToAccidentalName = {
#   cents   name
    0:     'natural',
    25:    'natural-up',
    50:    'quarter-sharp',
    75:    'sharp-down',
    100:   'sharp',
    125:   'sharp-up',
    150:   'three-quarters-sharp',
    -25:   'natural-down',
    -50:   'quarter-flat',
    -75:   'flat-up',
    -100:  'flat',
    -125:  'flat-down',
    -150:  'three-quarters-flat'
}


def accidental_name(alteration_cents: int, semitone_divisions=4) -> str:
    """
    The name of the accidental corresponding to the given cents

    Args:
        alteration_cents: 100 = sharp, -50 = quarter-flat, etc.
        semitone_divisions: number of divisions of the semitone

    Returns:
        the name of the corresponding accidental, as string

    ==========  ==================
    cents       alteration name
    ==========  ==================
          0     natural
         25     natural-up
         50     quarter-sharp
         75     sharp-down
        100     sharp
        125     sharp-up
        150     three-quarters-sharp

         -25    natural-down
         -50    quarter-flat
         -75    flat-up
        -100    flat
        -125    flat-down
        -150    three-quarters-flat
    ==========  ==================

    .. seealso:: :func:`construct_notename`, :func:`split_notename`
    """
    assert semitone_divisions in {1, 2, 4}, "semitone_divisions should be 1, 2, or 4"
    centsResolution = 100 // semitone_divisions
    alteration_cents = round(alteration_cents / centsResolution) * centsResolution
    return _centsToAccidentalName[alteration_cents]


def _roundres(x:float, resolution:float) -> float:
    return round(x/resolution)*resolution


def vertical_position(note: str) -> int:
    """
    Return the vertical notated position of a note

    The only relevant information for the vertical position
    is the octave and the diatonic pitch class. So, 4G# and 4G
    have the same vertical position, 4Ab and 4G# do not (the vertical
    position of 4Ab is 4*7+6=34, for 4G# it is 33)

    .. seealso:: :func:`notated_pitch`, :func:`notated_interval`
    """
    notated = notated_pitch(note)
    return notated.vertical_position


def vertical_position_to_note(pos: int) -> str:
    """
    Given a vertical position as an integer, returns the corresponding (diatonic) note

    Args:
        pos: the position as index, where 0 is C

    Returns:
        the note corresponding to the given vertical position

    >>> vertical_position_to_note(2)
    0E
    >>> vertical_position_to_note(0)
    0C

    """
    # CDEFGAB
    # 0123456
    octave = pos // 7
    diatonic_step = pos % 7
    step = "CDEFGAB"[diatonic_step]
    return f"{octave}{step}"


def notated_pitch(pitch: Union[float, str], semitone_divisions=4) -> NotatedPitch:
    """
    Convert a note or a (fractional) midinote to a NotatedPitch

    Args:
        pitch: a midinote as float (60=4C), or a notename
        semitone_divisions: number of divisions per semitone (only relevant
            when passing a midinote as pitch

    Returns:
        the corresponding pitch as NotatedPitch

    .. seealso:: :func:`split_notename`, :class:`NotatedPitch`

    Example
    ~~~~~~~

        >>> notated_pitch("4C#+15")
        NotatedPitch(octave=4, diatonic_index=0, diatonic_name='C', chromatic_index=1,
                     chromatic_name='C#', diatonic_alteration=1.15, chromatic_alteration=0.15,
                     accidental_name='sharp-up')
        >>> notated_pitch("4Db+15")
        NotatedPitch(octave=4, diatonic_index=1, diatonic_name='D', chromatic_index=1,
                     chromatic_name='Db', diatonic_alteration=-0.85, chromatic_alteration=0.15,
                     accidental_name='flat-up')

    """
    if isinstance(pitch, (int, float)):
        pitch = _roundred(pitch, 1/semitone_divisions)
    return _notated_pitch_notename(pitch)


@_cache
def _notated_pitch_notename(notename: str) -> NotatedPitch:
    parts = split_notename(notename)
    diatonic_index = 'CDEFGABC'.index(parts.diatonic_name)
    chromatic_note = parts.diatonic_name + parts.alteration
    cents = parts.cents_deviation
    diatonic_alteration = (alteration_to_cents(parts.alteration)+cents) / 100
    return NotatedPitch(octave=parts.octave,
                        diatonic_index=diatonic_index,
                        diatonic_name=parts.diatonic_name,
                        chromatic_index=_pitchclass_chromatic[chromatic_note],
                        chromatic_name=chromatic_note,
                        diatonic_alteration=diatonic_alteration,
                        chromatic_alteration=cents/100,
                        accidental_name=accidental_name(int(diatonic_alteration*100)))


@_cache
def notename_upper(notename: str) -> str:
    """
    Convert from 4eb to 4Eb or from eb4 to Eb4

    Args:
        notename: the notename to convert

    Returns:
        the uppercase version of notename

    """
    parts = split_notename(notename)
    return construct_notename(parts.octave, parts.diatonic_name, parts.alteration, parts.cents_deviation)


def pitchclass(notename: str, semitone_divisions=1) -> int:
    """
    Returns the pitchclass of a given note, rounded to the nearest semitone division

    This index is independent of the pitche's octave.
    For chromatic resolotion (semitone_divisions=1), 4C has a pitchclass of 0
    (the same as any other C), 4C# and 4Db have a pitchclass of 1, 4D a pitchclass
    of 2, etc. If semitone_divisions is 2, then 4C has still a pitchclass of ß but
    4C# would have a pitchclass of 2, while 4C+ and 4Db- would result in a pitchclass
    of 1. Enharmonic pitches (4C# and 4Db) result in the same pitchclass.

    Args:
        notename: the pitch as notename
        semitone_divisions: the number of divisions per semitone
            (1=chromatic, 2=quarter tones, ...)

    Returns:
        the pitch-class index.


    """
    notated = notated_pitch(notename)
    if semitone_divisions == 1:
        notated.chromatic_index
    return notated.microtone_index(semitone_divisions=semitone_divisions)


def notes2ratio(n1: Union[float, str], n2: Union[float, str], maxdenominator=16
                ) -> tuple[int, int]:
    """
    Find the ratio between n1 and n2

    Args:
        n1: first note (a midinote or a notename)
        n2: second note (a midinote or a notename)
        maxdenominator: the maximum denominator possible

    Returns:
        a Fraction with the ratio between the two notes

    NB: to obtain the ratios of the harmonic series, the second note
        should match the intonation of the corresponding overtone of
        the first note

    ======  =======   =====
    Note 1  Note 2    Ratio
    ======  =======   =====
    C4      D4        8/9
    C4      Eb4+20    5/6
    C4      E4        4/5
    C4      F#4-30    5/7
    C4      G4        2/3
    C4      A4        3/5
    C4      Bb4-30    4/7
    C4      B4        8/15
    ======  =======   =====

    .. seealso:: :func:`ratio2interval`
    
    """
    f1 = n2f(n1) if isinstance(n1, str) else m2f(n1)
    f2 = n2f(n2) if isinstance(n2, str) else m2f(n2)
    from fractions import Fraction
    fraction = Fraction.from_float(f1/f2).limit_denominator(maxdenominator)
    return fraction.numerator, fraction.denominator



# --- Global functions ---

_converter = PitchConverter()
midi_to_note_parts = _converter.midi_to_note_parts
set_reference_freq = _converter.set_reference_freq
get_reference_freq = _converter.get_reference_freq
f2m = _converter.f2m
m2f = _converter.m2f
m2n = _converter.m2n
n2f = _converter.n2f
f2n = _converter.f2n
freq_round = _converter.freq_round
normalize_notename = _converter.normalize_notename
str2midi = _converter.str2midi
as_midinotes = _converter.as_midinotes


# --- Amplitude converters ---

def db2amp(db: float) -> float:
    """
    convert dB to amplitude (0, 1)

    Args:
        db: a value in dB

    .. seealso:: :func:`amp2db`
    """
    return 10.0 ** (0.05 * db)


def amp2db(amp: float) -> float:
    """
    convert amp (0, 1) to dB

    ``20.0 * log10(amplitude)``

    Args:
        amp: the amplitude between 0 and 1

    Returns: 
        the corresponding amplitude in dB

    .. seealso:: :func:`db2amp`
    """
    amp = max(amp, _EPS)
    return math.log10(amp) * 20


def _test_enharmonic():
    assert (result := enharmonic("4E+")) == "4F-", f"got {result}"
    assert (result := enharmonic("4F#")) == "4Gb", f"got {result}"
    assert (result := enharmonic("4C+")) == "4Db-", f"got {result}"
    assert (result := enharmonic("4G-")) == "4F#+", f"got {result}"
    assert (result := enharmonic("4G+60")) == "4Ab-40", f"got {result}"
    assert (result := enharmonic("4E+25")) == "4E+25", f"got {result}"
    assert (result := enharmonic("5Eb-55")) == "5D+45", f"got {result}"
    assert (result := enharmonic("4G-25")) == "4G-25", f"got {result}"
    assert (result := enharmonic("4C-25")) == "4C-25", f"got {result}"
    assert (result := enharmonic("4C-")) == "3B+", f"got {result}"
    assert (result := enharmonic("3B-")) == "3A#+", f"got {result}"
    assert (result := enharmonic("4F-55")) == "4E+45", f"got {result}"


def _tests():
    _test_enharmonic()
