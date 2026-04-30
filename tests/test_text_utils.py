from app.core.text_utils import compact_whitespace, remove_overlap


def test_remove_overlap():
    assert remove_overlap("hello everyone", "everyone welcome back") == "welcome back"


def test_compact_whitespace():
    assert compact_whitespace("  a   b \n c ") == "a b c"
