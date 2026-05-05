from pathlib import Path

from app.config import SettingsManager
from app.models import AppSettings, TranslationDomain
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
    settings = AppSettings()
    settings.recognition.translation_domain = TranslationDomain.ELECTRONICS
    settings.recognition.transcribe_base_url = "https://asr.example.com/v1"
    settings.recognition.translate_base_url = "https://translate.example.com/v1"
    settings.recognition.translation_glossary = "USB-C=Type-C 口\n"
    settings.recognition.translation_names = "Alex=阿力克斯\n"
    mgr.save(settings)

    loaded = mgr.load()
    assert loaded.recognition.translation_domain == TranslationDomain.ELECTRONICS
    assert loaded.recognition.transcribe_base_url == "https://asr.example.com/v1"
    assert loaded.recognition.translate_base_url == "https://translate.example.com/v1"
    assert "USB-C" in loaded.recognition.translation_glossary
    assert "Alex" in loaded.recognition.translation_names


def test_settings_load_legacy_base_url_into_both_fields(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text(
        '{"recognition":{"base_url":"https://legacy.example.com/v1","translation_domain":"beauty"}}',
        encoding="utf-8",
    )

    loaded = SettingsManager(path).load()

    assert loaded.recognition.transcribe_base_url == "https://legacy.example.com/v1"
    assert loaded.recognition.translate_base_url == "https://legacy.example.com/v1"


def test_settings_migrate_legacy_shared_api_key_names(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text(
        '{"transcribe_api_key_name":"default","translate_api_key_name":"default"}',
        encoding="utf-8",
    )

    loaded = SettingsManager(path).load()

    assert loaded.transcribe_api_key_name == "transcribe"
    assert loaded.translate_api_key_name == "translate"


def test_translator_system_prompt_includes_domain_and_tables():
    translator = OpenAICompatibleTranslator(
        base_url="http://localhost/v1",
        api_key="x",
        model="m",
        timeout_seconds=30.0,
        translation_domain=TranslationDomain.BEAUTY,
        glossary_text="Retinol=视黄醇",
        names_text="Mia=米娅",
    )
    prompt = translator._system_prompt()
    assert "美妆" in prompt
    assert "Retinol=视黄醇" in prompt
    assert "Mia=米娅" in prompt

    translator_no_domain = OpenAICompatibleTranslator(
        base_url="http://localhost/v1",
        api_key="x",
        model="m",
        timeout_seconds=30.0,
        translation_domain=TranslationDomain.NONE,
    )
    assert "【领域：" not in translator_no_domain._system_prompt()
