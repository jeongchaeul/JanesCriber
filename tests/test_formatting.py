from janescriber.formatting import render_json, render_srt, render_text, render_transcript, render_vtt, timestamp


def test_timestamp_has_millisecond_precision():
    assert timestamp(3661.234) == "01:01:01.234"


def test_render_text_has_timestamped_segments():
    value = render_text({"language": "en", "segments": [{"start": 0, "end": 1.25, "text": " Hello world. "}]}, "demo.mp4", "turbo")
    assert "[00:00:00.000 --> 00:00:01.250]\n\n>Hello world." in value
    assert "Source: demo.mp4" in value


def test_render_srt_uses_subrip_timestamps():
    value = render_srt({"segments": [{"start": 0, "end": 1.25, "text": " Hello world. "}]}, "demo.mp4", "turbo")
    assert value == "1\n00:00:00,000 --> 00:00:01,250\nHello world.\n"


def test_render_vtt_has_webvtt_header():
    value = render_vtt({"segments": [{"start": 0, "end": 1.25, "text": "Hello world."}]}, "demo.mp4", "turbo")
    assert value.startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.250\nHello world.\n")


def test_render_json_preserves_segment_and_word_metadata():
    value = render_json(
        {"language": "en", "text": "Hello world.", "segments": [{"start": 0, "end": 1, "text": "Hello world."}], "words": [{"word": "Hello", "start": 0, "end": 0.5}]},
        "demo.mp4",
        "Whisper: turbo",
    )
    assert '"format": "janescriber.transcript.v1"' in value
    assert '"word": "Hello"' in value


def test_render_transcript_accepts_extension_style_format():
    value = render_transcript({"segments": []}, "demo.mp4", "turbo", ".vtt")
    assert value == "WEBVTT\n\n"
