import subprocess
import sys
import threading
import time

import pytest

from janescriber.cancellation import PipelineAborted, check_cancelled, run_cancellable_subprocess


def test_check_cancelled_supports_event():
    event = threading.Event()
    check_cancelled(event)
    event.set()
    with pytest.raises(PipelineAborted):
        check_cancelled(event)


def test_subprocess_can_be_cancelled_promptly():
    event = threading.Event()

    def cancel_later():
        time.sleep(0.12)
        event.set()

    canceller = threading.Thread(target=cancel_later)
    canceller.start()
    started = time.monotonic()
    with pytest.raises(PipelineAborted):
        run_cancellable_subprocess(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            event,
            poll_interval=0.02,
        )
    canceller.join()
    assert time.monotonic() - started < 2.5


def test_subprocess_reports_failure():
    with pytest.raises(subprocess.CalledProcessError):
        run_cancellable_subprocess([sys.executable, "-c", "raise SystemExit(7)"])
