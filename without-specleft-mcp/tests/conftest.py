from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.app_factory import create_app


@pytest.fixture()
def client():
    app = create_app("sqlite:///:memory:")
    return TestClient(app)
