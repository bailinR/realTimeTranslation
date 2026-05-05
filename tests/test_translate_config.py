from pathlib import Path

from app.config import SettingsManager
from app.models import AppSettings, RecognitionConfig, TranslationDomain
from app.translate.openai_compatible import OpenAICompatibleTranslator, parse_translation_table_lines


def test_parse_translation_table_lines():
    raw = """
  a=b
# comment
  x = y

last=z
""" * 20
    lines = parse_translation_table_lines(raw, max_lines=5)
    assert lines == ["a=b", "x = y", "last=z", "a=b", "x = y"]


def test_settings_roundtrip_domain_glossary(tmp_path: Path):
    path = tmp_path / "settings.json"
    mgr = SettingsManager(path)
    s = AppSettings()
    s.recognition.translation_domain = TranslationDomain.ELECTRONICS
    s.recognition.translation_glossary = "USB-C=Type-C 口\n"
    s.recognition.translation_names = "Alex=阿力克斯\n"
    mgr.save(s)
    loaded = mgr.load()
    assert loaded.recognition.translation_domain == TranslationDomain.ELECTRONICS
    assert "USB-C" in loaded.recognition.translation_glossary
    assert "Alex" in loaded.recognition.translation_names


def test_translator_system_prompt_includes_domain_and_tables():
    t = OpenAICompatibleTranslator(
        base_url="http://localhost/v1",
        api_key="x",
        model="m",
        timeout_seconds=30.0,
        translation_domain=TranslationDomain.BEAUTY,
        glossary_text="Retinol=视黄醇",
        names_text="Mia=米娅",
    )
    p = t._system_prompt()
    assert "美妆" in p
    assert "Retinol=视黄醇" in p
    assert "Mia=米娅" in p
    t2 = OpenAICompatibleTranslator(
        base_url="http://localhost/v1",
        api_key="x",
        model="m",
        timeout_seconds=30.0,
        translation_domain=TranslationDomain.NONE,
    )
    assert "【领域：" not in t2._system_prompt()
