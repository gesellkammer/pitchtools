"""
Set of routines to work with musical pitches, convert to and from frequencies, 
notenames, etc.

Global settings vs Converter objects
====================================

In order to customize settings like the frequency of A4, it is possible
to either set that value globally (via, for example, :func:`pitchtools.set_reference_freq`)
or create a custom :class:`~pitchtools.Converter`


Example
-------

.. code::

    # Set the value globally
    >>> set_reference_freq(443)
    >>> n2f("A4")
    443.0

    # Create a Converter object
    >>> cnv = Converter(a4=435)
    >>> print(cnv.n2f("4C"))
    258.7

"""

from __future__ import annotations
import math
import sys
import re as _re
from typing import Tuple, List, NamedTuple, Union as U


_EPS = sys.float_info.epsilon


number_t = U[int, float]

_flats  = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B", "C"]
_sharps = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B", "C"]

_notes2 = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

_r1 = _re.compile(r"(?P<pch>[A-Ha-h][b|#]?)(?P<oct>[-]?[\d]+)(?P<micro>[-+><↓↑][\d]*)?")
_r2 = _re.compile(r"(?P<oct>[-]?\d+)(?P<pch>[A-Ha-h][b|#]?)(?P<micro>[-+><↓↑]\d*)?")


class NoteParts(NamedTuple):
    """
    Attributes:
        octave (int): octave number, 4=central octave
        noteName (str: "C", "D", "E", ... (diatonic step)
        alteration (str): the alteration as str, "#", "b", "+", "-", ">", "<"
        centsDeviation (int): number of cents deviation from the chromatic pitch
    """
    octave: int
    noteName: str
    alteration: str
    centsDeviation: int

    @property
    def alterationCents(self) -> int:
        return alteration_to_cents(self.alteration)



class ParsedMidinote(NamedTuple):
    """
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


class NotatedPitch(NamedTuple):
    """
    Attributes:
        octave: the octave (4=central octave)
        diatonic_index: 0=C, 1=D, 2=E, ...
        diatonic_step: "C", "D", "E", ...
        chromatic_index: 0=C, 1=C#, 2=D, ...
        chromatic_step: "C", "Db", ...
        diatonic_alteration: for C# this would be 1.0, for Db this would be -1.0
        chromatic_alteration: for C#+50 this would be 0.5
        accidental_name: the name of the accidental used ('natural', 'natural-up','quarter-sharp', etc.)
    """
    octave: int
    diatonic_index: int
    diatonic_step: str
    chromatic_index: int
    chromatic_step: str
    diatonic_alteration: float
    chromatic_alteration: float
    accidental_name: str


class Converter:
    """
    Convert between midinote, frequency and notename.

    Args:
        a4: the reference frequency
        eightnote_symbol: if True, a special symbol is used
            (">", "<") when a note is exactly 25 cents higher
            or lower (for example, "4C>"). Otherwise, a notename
            would be, for example, "4C+25"
    """

    def __init__(self, a4=442.0, eightnote_symbol=True):
        self.a4 = a4
        self.eighthnote_symbol = eightnote_symbol

    def set_reference_freq(self, a4:float) -> None:
        """
        Set the reference freq. (the freq. of A4) for this converter

        Args:
            a4: the freq. of A4 in Hz
        """
        self.a4 = a4

    def get_reference_freq(self) -> float:
        """
        Get the reference frequency for this converter

        Returns:
            the freq. of A4
        """
        return self.a4

    def f2m(self, freq: float) -> float:
        """
        Convert a frequency in Hz to a midi-note

        Args:
            freq: the frequency to convert, in Hz

        Returns:
            the midi note corresponding to freq

        **See also**: :meth:`~Converter-set_reference_freq`
        """
        if freq<9:
            return 0
        return 12.0*math.log(freq/self.a4, 2)+69.0

    def freqround(self, freq:float) -> float:
        """
        Round the freq. to the nearest midinote

        Args:
            freq: the freq. to round

        Returns:
            the rounded frequency
        """
        return self.m2f(round(self.f2m(freq)))

    def m2f(self, midinote: float) -> float:
        """
        Convert a midi-note to a frequency

        Args:
            midinote: the midinote to convert to frequency

        Returns:
            the freq. corresponding to midinote
        """
        return 2**((midinote-69)/12.0)*self.a4

    def m2n(self, midinote: float) -> str:
        """
        Convert midinote to notename

        Args:
            midinote: a midinote (60=C4)

        Returns:
            the notename corresponding to midinote.

        """
        octave, note, microtonal_alteration, cents = self.midi_to_note_parts(midinote)
        if cents == 0:
            return str(octave)+note+microtonal_alteration
        if cents>0:
            if cents<10:
                return f"{octave}{note}{microtonal_alteration}+0{cents}"
            return f"{octave}{note}{microtonal_alteration}+{cents}"
        else:
            if -10<cents:
                return f"{octave}{note}{microtonal_alteration}-0{abs(cents)}"
            return f"{octave}{note}{microtonal_alteration}{cents}"

    def n2m(self, note: str) -> float:
        """ 
        Convert a notename to a midinote 

        Args:
            note: the notename

        Returns:
            the midinote corresponding to note
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

    def pianofreqs(self, start="A0", stop="C8") -> List[float]:
        """
        Generate an array of the frequencies representing all the piano keys

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

    def asmidi(self, x:U[int, float, str]) -> float:
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
            >>> cnv = Converter()
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

        Args:
            s: pitch describes as a string. Possible values: "100hz", "4F+20hz", "8C-4hz"

        Returns:
            the corresponding midinote

        **NB**: The hz part must be at the end
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

    def midi_to_note_parts(self, midinote: float) -> NoteParts:
        """
        Convert a midinote into its parts as a note

        Args:
            midinote: the midinote to analyze

        Returns:
            a NoteParts instance, a named tuple with the fields: `octave`, `noteName`,
            `alteracion` and `centsDeviation`

        """
        i = int(midinote)
        micro = midinote-i
        octave = int(midinote/12.0)-1
        ps = int(midinote%12)
        cents = int(micro*100+0.5)
        if cents == 0:
            return NoteParts(octave, _sharps[ps], "", 0)
        elif cents == 50:
            if ps in (1, 3, 6, 8, 10):
                return NoteParts(octave, _sharps[ps+1], "-", 0)
            return NoteParts(octave, _sharps[ps], "+", 0)
        elif cents == 25 and self.eighthnote_symbol:
            return NoteParts(octave, _sharps[ps], ">", 0)
        elif cents == 75 and self.eighthnote_symbol:
            ps += 1
            if ps>11:
                octave += 1
            if ps in (1, 3, 6, 8, 10):
                return NoteParts(octave, _flats[ps], "<", 0)
            else:
                return NoteParts(octave, _sharps[ps], "<", 0)
        elif cents>50:
            cents = 100-cents
            ps += 1
            if ps>11:
                octave += 1
            return NoteParts(octave, _flats[ps], "", -cents)
        else:
            return NoteParts(octave, _sharps[ps], "", cents)

    def normalize_notename(self, notename: str) -> str:
        """ 
        Convert notename to its canonical form 

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


def n2m(note: str) -> float:
    """
    Convert a notename to a midinote

    Args:
        note: the notename

    Returns:
        the corresponding midi note

    Two formats are supported:

    * 1st format: ``C#2``, ``D4``, ``Db4+20``, ``C4>``, ``Eb5<``
    * 2nd format: ``2C#``, ``4D+``, ``7Eb-14``

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

    =====================    ========
    Microtonal-Alteration    Cents
    =====================    ========
    ``+``                    +50
    ``-``                    -50
    ``>``                    +25
    ``<``                    -25
    =====================    ========

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


def parse_midinote(midinote: float) -> ParsedMidinote:
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
    return ParsedMidinote(ps, round(micro, 2), octave, pitchname)


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

    See Also:
        `quantize_notename`

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


    See Also:
        `quantize_midinote`
    """

    octave, letter, alter, cents = split_notename(notename)
    cents = int(round(cents/100 * divisions_per_semitone) / divisions_per_semitone * 100)
    if cents >= 100 or cents <= -100:
        notename = m2n(round(n2m(notename) * divisions_per_semitone) / divisions_per_semitone)
        octave, letter, alter, cents = split_notename(notename)
    return construct_notename(octave, letter, alter, cents)


def construct_notename(octave:int, letter:str, alter:U[int, str], cents:int,
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


def _parse_centstr(centstr: str) -> int:
    if not centstr:
        return 0
    cents = _centsrepr.get(centstr)
    if cents is None:
        cents = int(centstr)
    return cents


def split_notename(notename: str) -> Tuple[int, str, str, int]:
    """
    Return (octave, letter, alteration (#, b), cents)

    Microtonal alterations, like "+", "-", ">", "<" are resolved
    into cents alterations

    =======    ===================
     Input           Output
    =======    ===================
    4C#+10     (4, "C", "#", 10)
    Eb4-15     (4, "E", "b", -15)
    4C+        (4, "C", "", 50)
    5Db<       (5, "D", "b", -25)
    =======    ===================
    """
    if not notename[0].isdecimal():
        # C#4-10
        cursor = 1
        letter = notename[0]
        l1 = notename[1]
        if l1 == "#":
            alter = "#"
            octave = int(notename[2])
            cursor = 3
        elif l1 == "b":
            alter = "b"
            octave = int(notename[2])
            cursor = 3
        else:
            alter = ""
            octave = int(notename[1])
            cursor = 2
        centstr = notename[cursor:]
        cents = _parse_centstr(centstr)
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
    return octave, letter.upper(), alter, cents


def split_cents(notename: str) -> Tuple[str, int]:
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

    """
    octave, letter, alter, cents = split_notename(notename)
    alterchar = "b" if alter == -1 else "#" if alter == 1 else ""
    return str(octave) + letter + alterchar, cents


def enharmonic(notename: str) -> str:
    """
    Return the enharmonic version of notename. 

    Notes without an alteration have no enharmonic 
    (double alterations are never used)


    Args:
        notename: the notename to find an enharmonic to

    Returns:
        the enharmonic version of the note (this can be the
        same as the original)

    ==========     ============
    original       enharmonic
    ==========     ============
    4C+50          4Db-50
    4A+25          unchanged
    4G#+25         4Ab+25
    4Eb-25         4D#-25
    4G+30          unchanged
    ==========     ============

    """
    midinote = n2m(notename)
    diatonicsteps = "CDEFGAB"
    if int(midinote) == midinote:
        return notename
    octave, letter, alteration, cents = split_notename(notename)
    sign = "+" if cents > 0 else "-" if cents < 0 else ""
    pitchidx = diatonicsteps.index(letter)
    if alteration != 0:
        # a black key
        if alteration == 1:
            # turn sharp to flat
            basenote = diatonicsteps[pitchidx+1] + "b"
            return f"{octave}{basenote}{sign}{abs(cents)}"
        else:
            # turn flat into sharp
            basenote = diatonicsteps[pitchidx-1] + "#"
            return f"{octave}{basenote}{sign}{abs(cents)}"
    else:
        if cents == 50:
            # 4D+50 -> 4Eb-50
            # 4B+50 -> 5C-50
            if letter == "B":
                return f"{octave+1}C-"
            basenote = diatonicsteps[pitchidx+1] + "b"
            return f"{octave}{basenote}-"
        elif cents == -50:
            # 4D-50 -> 4C#+50
            # 4C-50 -> 3B+50
            if letter == "C":
                return f"{octave-1}B+"
            basenote = diatonicsteps[pitchidx+1]+"b"
            return f"{octave}{basenote}-"
        else:
            return notename


def pitch_round(midinote: float, semitoneDivisions=4) -> Tuple[str,int]:
    """
    Round midinote to the next (possibly microtonal) pitch

    Returns the rounded notename and the cents deviation
    from the original pitch to the next semitone

    Args:
        midinote: the midinote to round, as float
        semitoneDivisions: the number of division per semitone

    Returns:
        a tuple (rounded note, cents deviation)

    Example
    =======

    .. code::
        
        >>> pitch_round(60.1)
        ("4C", 10)
        >>> pitch_round(60.75)
        ("4D<", -25)
        
    """
    rounding_factor = 1 / semitoneDivisions
    rounded_midinote = round(midinote/rounding_factor)*rounding_factor
    notename = m2n(rounded_midinote)
    basename, cents = split_cents(notename)
    mididev = midinote-n2m(basename)
    centsdev = int(round(mididev*100))
    return notename, centsdev


def freq2mel(freq: float) -> float:
    """
    Convert a frequency to its place in the mel-scale

    .. note::
        The mel scale is a perceptual scale of pitches judged by listeners to be
        equal in distance from one another
    """
    return 1127.01048 * math.log(1. + freq/700)


def mel2freq(mel:float) -> float:
    """
    Convert a position in the mel-scale to its corresponding frequency

    Args:
        mel: the mel index (can be fractional)

    Returns:
        the corresponding freq. in Hz


    .. note::
        The mel scale is a perceptual scale of pitches judged by listeners to be
        equal in distance from one another

    """
    return 700. * (math.exp(mel / 1127.01048) - 1.0)

_centsToAccidentalName = {
# cents   name
    0:   'natural',
    25:  'natural-up',
    50:  'quarter-sharp',
    75:  'sharp-down',
    100: 'sharp',
    125: 'sharp-up',
    150: 'three-quarters-sharp',

    -25: 'natural-down',
    -50: 'quarter-flat',
    -75: 'flat-up',
    -100:'flat',
    -125:'flat-down',
    -150:'three-quarters-flat'
}


def accidental_name(alterationCents: int, semitoneDivisions=4) -> str:
    """
    The name of the accidental corresponding to the given cents

    Args:
        alterationCents: 100 = sharp, -50 = quarter-flat, etc.
        semitoneDivisions: number of divisions of the semitone

    Returns:
        the name of the corresponding accidental, as string

    Names::

        cents       alteration name
        ---------------------------
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
    """
    assert semitoneDivisions in {1, 2, 4}, "semitoneDivisions should be 1, 2, or 4"
    if alterationCents < -150 or alterationCents > 150:
        raise ValueError(f"alterationCents should be between -150 and 150, "
                         f"got {alterationCents}")
    centsResolution = 100 // semitoneDivisions
    alterationCents = round(alterationCents / centsResolution) * centsResolution
    return _centsToAccidentalName[alterationCents]


def _roundres(x:float, resolution:float) -> float:
    return round(x/resolution)*resolution


def notated_pitch(midinote: float, divsPerSemitone=4) -> NotatedPitch:
    """
    Convert a (fractional) midinote to a NotatedPitch

    Args:
        midinote: a midinote as float (60=4C)
        divsPerSemitone: number of divisions per semitone

    Returns:
        the corresponding pitch as NotatedPitch
    """
    rounded_midinote = _roundres(midinote, 1/divsPerSemitone)
    parsed_midinote = parse_midinote(rounded_midinote)
    notename = m2n(rounded_midinote)
    octave, letter, alter, cents = split_notename(notename)
    basename, cents = split_cents(notename)
    chromaticStep = letter + alter
    diatonicAlteration = (alteration_to_cents(alter)+cents) / 100
    try:
        diatonic_index = "CDEFGAB".index(letter)
    except ValueError:
        raise ValueError(f"note step is not diatonic: {letter}")

    return NotatedPitch(octave=octave,
                        diatonic_index=diatonic_index,
                        diatonic_step=letter,
                        chromatic_index=parsed_midinote.pitchindex,
                        chromatic_step=chromaticStep,
                        diatonic_alteration=diatonicAlteration,
                        chromatic_alteration=cents/100,
                        accidental_name=accidental_name(int(diatonicAlteration*100)))


# --- Global functions ---

_converter = Converter()
midi_to_note_parts = _converter.midi_to_note_parts
set_reference_freq = _converter.set_reference_freq
get_reference_freq = _converter.get_reference_freq
f2m = _converter.f2m
m2f = _converter.m2f
m2n = _converter.m2n
n2f = _converter.n2f
f2n = _converter.f2n
freqround = _converter.freqround
normalize_notename = _converter.normalize_notename
str2midi = _converter.str2midi


# --- Amplitude converters ---

def db2amp(db: float) -> float:
    """
    convert dB to amplitude (0, 1)

    Args:
        db: a value in dB
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
    """
    amp = max(amp, _EPS)
    return math.log10(amp) * 20

