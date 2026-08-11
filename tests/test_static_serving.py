"""Regression tests for the SPA catch-all route.

An encoded traversal (`..%2f`) survives URL decoding where a plain `../` is
normalized away by clients — so the catch-all needs its own containment check.
"""
import pytest
from starlette.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.skipif(
    not any(r.name == "serve_spa" for r in app.routes),
    reason="SPA route only registers when frontend/dist has been built",
)


@pytest.fixture
def client():
    return TestClient(app)


class TestPathTraversal:
    @pytest.mark.parametrize(
        "path,marker",
        [
            ("/..%2f..%2f.env", "SMTP_HOST"),
            ("/../../.env", "SMTP_HOST"),
            ("/..%2f..%2fbackend%2fconfig.py", "BaseSettings"),
            ("/..%2f..%2f..%2f..%2f..%2f..%2fetc%2fpasswd", "root:"),
            ("/....%2f%2f.env", "SMTP_HOST"),
        ],
    )
    def test_traversal_never_leaks_file_contents(self, client, path, marker):
        assert marker not in client.get(path).text


class TestLegitimateServing:
    @pytest.mark.parametrize("path", ["/", "/index.html", "/some/spa/route"])
    def test_serves_spa_shell(self, client, path):
        r = client.get(path)
        assert r.status_code == 200
        assert "<!doctype html>" in r.text.lower()

    def test_serves_real_static_asset(self, client):
        r = client.get("/favicon.svg")
        assert r.status_code == 200
        assert len(r.content) > 100
