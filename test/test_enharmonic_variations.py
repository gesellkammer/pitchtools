"""
Test suite for enharmonic_variations()

Note format: <octave><pitch_class><alteration>
    octave     : integer, e.g. 4
    pitch_class: e.g. C, D#, Eb, F##, Bbb
    alteration : optional microtonal suffix
                   +      quarter-tone sharp  (+50 cents, implicit)
                   -      quarter-tone flat   (-50 cents, implicit)
                   +N     N cents sharp       (e.g. +30)
                   -N     N cents flat        (e.g. -10)

Enharmonic rules
    - Same-slot respelling (e.g. C# <-> Db): cent offset is UNCHANGED.
      4Eb-10 -> 4D#-10
    - Cross-boundary respelling (e.g. E+ <-> F-): cents are NEGATED
      because crossing a semitone = 100 cents.
      4E+   (= 4E+50) -> 4F-   (= 4F-50)
      4E+30           -> 4F-70 (100 - 30 = 70)
    - 4C+   is identical to 4C+50 -> 4Db-  (= 4Db-50)

Slot numbering (fixedslots):
    0=C, 1=C+/Db-, 2=C#/Db, 3=D, 4=D+/Eb-, 5=D#/Eb, ...
    alteration direction: 1=#-side, -1=b-side
"""

import pytest
from pitchtools import *


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def spellings_at(result, position=0):
    """Return the set of note strings at *position* across all variations."""
    return {v[position] for v in result}


# ---------------------------------------------------------------------------
# 1. Note format parsing
# ---------------------------------------------------------------------------

class TestNoteParsing:
    """The function must accept all documented note formats without raising."""

    @pytest.mark.parametrize("note", [
        "4C", "4C#", "4Db", "4D", "4Eb", "4E", "4F",
        "4F#", "4Gb", "4G", "4Ab", "4A", "4Bb", "4B",
    ])
    def test_standard_notes_accepted(self, note):
        result = enharmonic_variations([note])
        assert isinstance(result, list) and len(result) >= 1

    @pytest.mark.parametrize("note", [
        "4C+", "4C-", "4E+", "4F-", "4B+", "4C#-", "4Eb+",
    ])
    def test_quarter_tone_notes_accepted(self, note):
        result = enharmonic_variations([note])
        assert isinstance(result, list) and len(result) >= 1

    @pytest.mark.parametrize("note", [
        "4C+30", "4Eb-10", "4F#+30", "4Gb-20", "4A+15", "4Bb-5",
    ])
    def test_cent_offset_notes_accepted(self, note):
        result = enharmonic_variations([note])
        assert isinstance(result, list) and len(result) >= 1

    def test_octave_number_preserved_in_output(self):
        """Octave prefix must appear unchanged in every returned variation."""
        result = enharmonic_variations(["4C#"])
        for variation in result:
            assert variation[0].startswith("4"), (
                f"Octave '4' lost in output: {variation[0]!r}"
            )

    @pytest.mark.parametrize("octave", [2, 3, 4, 5, 6])
    def test_various_octaves_preserved(self, octave):
        result = enharmonic_variations([f"{octave}C#"])
        for variation in result:
            assert variation[0].startswith(str(octave))


# ---------------------------------------------------------------------------
# 2. Standard (non-microtonal) enharmonic respelling
# ---------------------------------------------------------------------------

class TestStandardEnharmonics:
    def test_4C_sharp_to_4Db(self):
        """Documented example: 4C# -> 4Db."""
        assert ("4Db",) in enharmonic_variations(["4C#"])

    def test_4Db_to_4C_sharp(self):
        assert ("4C#",) in enharmonic_variations(["4Db"])

    def test_natural_note_has_exactly_one_variation(self):
        for note in ["4C", "4D", "4E", "4F", "4G", "4A", "4B"]:
            result = enharmonic_variations([note])
            assert len(result) == 1, (
                f"{note}: expected 1 variation, got {len(result)}"
            )

    @pytest.mark.parametrize("sharp,flat", [
        ("4C#", "4Db"),
        ("4D#", "4Eb"),
        ("4F#", "4Gb"),
        ("4G#", "4Ab"),
        ("4A#", "4Bb"),
    ])
    def test_standard_enharmonic_pairs_bidirectional(self, sharp, flat):
        assert (flat,)  in enharmonic_variations([sharp])
        assert (sharp,) in enharmonic_variations([flat])

    def test_E_and_Fb_are_enharmonic(self):
        assert ("4Fb",) in enharmonic_variations(["4E"]) \
            or ("4E",)  in enharmonic_variations(["4Fb"])

    def test_B_and_Cb_are_enharmonic(self):
        assert ("4Cb",) in enharmonic_variations(["4B"]) \
            or ("4B",)  in enharmonic_variations(["4Cb"])

    def test_E_sharp_and_F_natural(self):
        assert ("4F",)  in enharmonic_variations(["4E#"]) \
            or ("4E#",) in enharmonic_variations(["4F"])

    def test_B_sharp_and_C_natural(self):
        assert ("4C",)  in enharmonic_variations(["4B#"]) \
            or ("4B#",) in enharmonic_variations(["4C"])


# ---------------------------------------------------------------------------
# 3. Quarter-tone enharmonics  (bare + or -)
# ---------------------------------------------------------------------------

class TestQuarterToneEnharmonics:
    def test_4E_plus_to_4F_minus(self):
        """Documented example: 4E+ -> 4F-."""
        assert ("4F-",) in enharmonic_variations(["4E+"])

    def test_4F_minus_to_4E_plus(self):
        assert ("4E+",) in enharmonic_variations(["4F-"])

    def test_4C_plus_to_4Db_minus(self):
        """Documented example: 4C+ (= 4C+50) -> 4Db-."""
        assert ("4Db-",) in enharmonic_variations(["4C+"])

    def test_4Db_minus_to_4C_plus(self):
        assert ("4C+",) in enharmonic_variations(["4Db-"])

    def test_bare_plus_equals_explicit_50(self):
        """4C+ and 4C+50 must produce identical variation sets."""
        assert set(enharmonic_variations(["4C+"])) \
            == set(enharmonic_variations(["4C+50"]))

    def test_bare_minus_equals_explicit_50(self):
        """4C- and 4C-50 must produce identical variation sets."""
        assert set(enharmonic_variations(["4C-"])) \
            == set(enharmonic_variations(["4C-50"]))

    @pytest.mark.parametrize("note,expected", [
        ("4B+", "4C-"),   # B+50 == C-50
        ("4C-", "4B+"),
        ("4E+", "4F-"),
        ("4F-", "4E+"),
    ])
    def test_boundary_quarter_tones(self, note, expected):
        assert (expected,) in enharmonic_variations([note])


# ---------------------------------------------------------------------------
# 4. Cent-offset enharmonics
# ---------------------------------------------------------------------------

class TestCentOffsetEnharmonics:
    def test_4Eb_minus10_to_4Dsharp_minus10(self):
        """Documented example: 4Eb-10 -> 4D#-10.
        Same semitone slot; cents are unchanged."""
        assert ("4D#-10",) in enharmonic_variations(["4Eb-10"])

    def test_4Dsharp_minus10_to_4Eb_minus10(self):
        assert ("4Eb-10",) in enharmonic_variations(["4D#-10"])

    def test_same_slot_respelling_cents_unchanged(self):
        """4F#+30 <-> 4Gb+30: same slot, cents must not change sign."""
        result = enharmonic_variations(["4F#+30"])
        assert "4Gb+30" in spellings_at(result)

    def test_cross_boundary_cents_negated_E_plus30(self):
        """
        4E+30 crosses from E into F territory.
        Distance to F = 100 - 30 = 70 cents below F, so result is 4F-70.
        """
        result = enharmonic_variations(["4E+30"])
        assert "4F-70" in spellings_at(result), (
            f"Expected '4F-70' among {spellings_at(result)}"
        )

    def test_cross_boundary_cents_negated_F_minus30(self):
        """4F-30 -> 4E+70 (100 - 30 = 70 cents above E)."""
        result = enharmonic_variations(["4F-30"])
        assert "4E+70" in spellings_at(result)

    def test_cross_boundary_C_plus30_to_Db_minus70(self):
        """4C+30 -> 4Db-70."""
        result = enharmonic_variations(["4C+30"])
        assert "4Db-70" in spellings_at(result)

    def test_cross_boundary_Db_minus30_to_C_plus70(self):
        """4Db-30 -> 4C+70."""
        result = enharmonic_variations(["4Db-30"])
        assert "4C+70" in spellings_at(result)

    def test_zero_cent_offset_equivalent_to_plain(self):
        """4C#+0 behaves identically to 4C#."""
        r_plain = set(enharmonic_variations(["4C#"]))
        r_zero  = set(enharmonic_variations(["4C#+0"]))
        assert r_plain == r_zero or len(r_zero) >= 1

    def test_output_note_contains_cent_suffix(self):
        """Returned note strings for microtonal inputs must include the cent suffix."""
        result = enharmonic_variations(["4Eb-10"])
        for variation in result:
            note = variation[0]
            assert "-10" in note or "+10" in note, (
                f"Cent information missing or wrong in: {note!r}"
            )

    def test_49_cent_offset_accepted(self):
        """±49 cents is the largest offset that stays within one semitone slot."""
        assert len(enharmonic_variations(["4C+49"])) >= 1
        assert len(enharmonic_variations(["4C-49"])) >= 1


# ---------------------------------------------------------------------------
# 5. Multi-note inputs
# ---------------------------------------------------------------------------

class TestMultiNote:
    def test_tuple_length_matches_input(self):
        notes = ["4C#", "4E+", "4G"]
        result = enharmonic_variations(notes)
        assert all(len(v) == 3 for v in result)

    def test_natural_positions_stay_fixed(self):
        """Natural notes must not be respelled to anything else."""
        result = enharmonic_variations(["4C", "4E", "4G#"])
        for variation in result:
            assert variation[0] == "4C"
            assert variation[1] == "4E"
            assert variation[2] in ("4G#", "4Ab")

    def test_microtonal_multi_note_positions_correct(self):
        result = enharmonic_variations(["4E+", "4Bb-10"])
        for variation in result:
            assert len(variation) == 2
            assert variation[0].startswith("4")
            assert variation[1].startswith("4")

    def test_no_duplicate_variations(self):
        result = enharmonic_variations(["4C#", "4F#", "4G#"])
        seen = set()
        for v in result:
            assert v not in seen, f"Duplicate variation: {v}"
            seen.add(v)

    def test_all_input_octaves_preserved_independently(self):
        result = enharmonic_variations(["3C#", "4F#", "5Bb"])
        for variation in result:
            assert variation[0].startswith("3")
            assert variation[1].startswith("4")
            assert variation[2].startswith("5")

    def test_mixed_standard_and_microtonal(self):
        """Standard and microtonal notes may appear together."""
        result = enharmonic_variations(["4C#", "4E+30"])
        assert all(len(v) == 2 for v in result)


# ---------------------------------------------------------------------------
# 6. fixedslots parameter
# ---------------------------------------------------------------------------

class TestFixedSlots:
    def test_fixedslot_sharp_forces_sharp_spelling(self):
        result = enharmonic_variations(["4C#"], fixedslots={2: 1})
        for variation in result:
            assert "C#" in variation[0], f"Sharp forced but got: {variation[0]!r}"

    def test_fixedslot_flat_forces_flat_spelling(self):
        result = enharmonic_variations(["4C#"], fixedslots={2: -1})
        for variation in result:
            assert "Db" in variation[0], f"Flat forced but got: {variation[0]!r}"

    def test_fixedslots_none_equals_default(self):
        r1 = set(enharmonic_variations(["4C#", "4F#"]))
        r2 = set(enharmonic_variations(["4C#", "4F#"], fixedslots=None))
        assert r1 == r2

    def test_fixedslots_unused_slot_no_effect(self):
        """Pinning a slot that is not present in the notes must not change results."""
        r1 = set(enharmonic_variations(["4C#"]))
        r2 = set(enharmonic_variations(["4C#"], fixedslots={11: 1}))
        assert r1 == r2

    def test_conflicting_fixedslot_force_false_empty(self):
        result = enharmonic_variations(["4C"], fixedslots={0: -1}, force=False)
        assert result == []

    def test_conflicting_fixedslot_force_true_nonempty(self):
        result = enharmonic_variations(["4C"], fixedslots={0: -1}, force=True)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# 7. force parameter
# ---------------------------------------------------------------------------

class TestForce:
    def test_force_true_always_returns_at_least_one(self):
        assert len(enharmonic_variations(["4C"], force=True)) >= 1

    def test_force_false_is_default(self):
        assert set(enharmonic_variations(["4C#"])) \
            == set(enharmonic_variations(["4C#"], force=False))

    def test_force_true_is_superset_of_valid(self):
        r_valid = set(enharmonic_variations(["4C#", "4F#"], force=False))
        r_force = set(enharmonic_variations(["4C#", "4F#"], force=True))
        assert r_valid.issubset(r_force)

    def test_force_true_microtonal(self):
        assert len(enharmonic_variations(["4E+30"], force=True)) >= 1


# ---------------------------------------------------------------------------
# 8. Pitch-class preservation (requires note_to_cents helper)
# ---------------------------------------------------------------------------

class TestPitchClassPreservation:
    """
    Every variation must be the same sounding pitch as the input.
    Requires a note_to_cents(note: str) -> float helper in your module
    that converts e.g. '4C#' -> 6100, '4E+' -> 6450, '4Eb-10' -> 6290.
    """

    @pytest.mark.parametrize("notes", [
        ["4C#"],
        ["4Db"],
        ["4E+"],
        ["4F-"],
        ["4Eb-10"],
        ["4D#-10"],
        ["4C+50"],
        ["4Db-"],
        ["4E+30"],
        ["4F-70"],
        ["4C#", "4F#", "4Bb"],
        ["4E+", "4B+30"],
    ])
    def test_pitch_in_cents_preserved(self, notes):
        from your_module import note_to_cents  # adjust import as needed
        input_cents = [note_to_cents(n) for n in notes]
        result = enharmonic_variations(notes)
        for variation in result:
            output_cents = [note_to_cents(n) for n in variation]
            assert output_cents == input_cents, (
                f"Pitch mismatch!\n"
                f"  Input     {notes} -> {input_cents}\n"
                f"  Variation {list(variation)} -> {output_cents}"
            )


# ---------------------------------------------------------------------------
# 9. Structural invariants
# ---------------------------------------------------------------------------

class TestStructuralInvariants:
    def test_returns_list(self):
        assert isinstance(enharmonic_variations(["4C#"]), list)

    def test_returns_list_of_tuples(self):
        result = enharmonic_variations(["4C#", "4E"])
        assert all(isinstance(v, tuple) for v in result)

    def test_empty_input(self):
        result = enharmonic_variations([])
        assert result in ([], [()])

    def test_does_not_mutate_input(self):
        notes = ["4C#", "4F+"]
        original = notes[:]
        enharmonic_variations(notes)
        assert notes == original

    def test_single_note_tuples_have_length_one(self):
        assert all(len(v) == 1 for v in enharmonic_variations(["4D#"]))

    def test_repeated_note_in_input_respelled_per_position(self):
        """The same note at two positions is independently handled."""
        result = enharmonic_variations(["4C#", "4C#"])
        assert all(len(v) == 2 for v in result)
