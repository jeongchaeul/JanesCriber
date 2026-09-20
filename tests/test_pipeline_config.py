import pytest

from janescriber.pipeline_config import TranscriptionConfig


def test_transcription_config_defaults_to_txt_output():
    assert TranscriptionConfig().output_format == "txt"


@pytest.mark.parametrize("output_format", ["txt", "srt", "vtt", "json", ".SRT"])
def test_transcription_config_accepts_supported_output_formats(output_format: str):
    assert TranscriptionConfig(output_format=output_format).output_format == output_format.lstrip(".").lower()


def test_transcription_config_rejects_unknown_output_format():
    with pytest.raises(ValueError, match="Unsupported transcript format"):
        TranscriptionConfig(output_format="html")
