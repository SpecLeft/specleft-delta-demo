import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app
from tests.helpers import reset_storage


@pytest.fixture()
def client():
    reset_storage()
    with TestClient(app) as test_client:
        yield test_client
