import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pendulum_kit.params import KitParameters  # noqa: E402
from fake_spoolman import FakeSpoolman  # noqa: E402


@pytest.fixture
def params():
    return KitParameters.load()


@pytest.fixture
def spoolman_url():
    with FakeSpoolman() as url:
        yield url


@pytest.fixture
def dead_url():
    """A local port where nothing is listening."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}"
