from janescriber.wav2vec_backend import _segments_from_offsets


def test_wav2vec_offsets_create_timestamped_words_and_segments():
    segments, words = _segments_from_offsets(
        "hello world.",
        [
            {"char": "h", "start_offset": 0, "end_offset": 2},
            {"char": "e", "start_offset": 2, "end_offset": 4},
            {"char": "l", "start_offset": 4, "end_offset": 6},
            {"char": "l", "start_offset": 6, "end_offset": 8},
            {"char": "o", "start_offset": 8, "end_offset": 10},
            {"char": "|", "start_offset": 10, "end_offset": 11},
            {"char": "w", "start_offset": 11, "end_offset": 13},
            {"char": "o", "start_offset": 13, "end_offset": 15},
            {"char": "r", "start_offset": 15, "end_offset": 17},
            {"char": "l", "start_offset": 17, "end_offset": 19},
            {"char": "d", "start_offset": 19, "end_offset": 21},
            {"char": ".", "start_offset": 21, "end_offset": 22},
        ],
        frame_count=22,
        duration=2.2,
        offset=3.0,
    )

    assert words[0]["word"] == "hello"
    assert words[0]["start"] == 3.0
    assert segments == [{"start": 3.0, "end": 5.2, "text": "hello world."}]
