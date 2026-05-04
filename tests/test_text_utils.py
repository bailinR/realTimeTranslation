from app.core.text_utils import compact_whitespace, remove_adjacent_overlap, remove_overlap


def test_remove_overlap():
    assert remove_overlap("hello everyone", "everyone welcome back") == "welcome back"


def test_compact_whitespace():
    assert compact_whitespace("  a   b \n c ") == "a b c"


def test_remove_adjacent_overlap_for_neighbor_chunks():
    previous = "and today we're going to test this camera in the rain"
    current = "test this camera in the rain and see whether it still works"

    assert remove_adjacent_overlap(previous, current) == "and see whether it still works"
