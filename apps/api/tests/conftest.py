"""Session-scoped DB initialisation for all tests."""
from __future__ import annotations

import pytest

from api.db import init_db


@pytest.fixture(autouse=True, scope="session")
def initialize_db():
    init_db()
