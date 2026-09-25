import pytest

import hazard_feeds
import weather


@pytest.fixture(autouse=True)
def fresh_cache():
    """Every test starts with empty forecast and hazard caches."""
    weather.clear_cache()
    hazard_feeds.clear_cache()
    yield
    weather.clear_cache()
    hazard_feeds.clear_cache()
