import pytest

import weather


@pytest.fixture(autouse=True)
def fresh_cache():
    """Every test starts with an empty forecast cache."""
    weather.clear_cache()
    yield
    weather.clear_cache()
