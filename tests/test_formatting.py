from janescriber.formatting import render_text, timestamp


def test_timestamp_has_millisecond_precision():
    assert timestamp(3661.234) == "01:01:01.234"


def test_render_text_has_timestamped_segments():
    value = render_text({"language": "en", "segments": [{"start": 0, "end": 1.25, "text": " Hello world. "}]}, "demo.mp4", "turbo")
    assert "[00:00:00.000 --> 00:00:01.250]\n\n>Hello world." in value
    assert "Source: demo.mp4" in value
