from pathlib import Path

import pytest


@pytest.fixture
def trending_html():
    return (Path(__file__).parent / "fixtures" / "trending.html").read_text(encoding="utf-8")
