from janescriber.languages import ALL_AVAILABLE_LANGUAGES, build_multilingual_prompt, normalize_language_codes


def test_normalize_language_codes_deduplicates_and_clears_auto():
    assert normalize_language_codes("id, en, ID, auto") == ["id", "en"]


def test_multilingual_prompt_anchors_non_english_decoder():
    primary, prompt = build_multilingual_prompt(["id", "en"])
    assert primary == "id"
    assert prompt is not None
    assert "Indonesian" in prompt
    assert "English" in prompt


def test_full_whisper_catalog_includes_tagalog_and_long_tail_languages():
    assert len(ALL_AVAILABLE_LANGUAGES) >= 99
    assert ALL_AVAILABLE_LANGUAGES["tl"].startswith("Tagalog")
    assert "haw" in ALL_AVAILABLE_LANGUAGES
    assert "yue" in ALL_AVAILABLE_LANGUAGES
