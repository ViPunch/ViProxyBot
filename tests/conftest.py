from pathlib import Path

import pytest


@pytest.fixture
def temp_config_path(tmp_path: Path) -> Path:
    return tmp_path / 'config.json'
