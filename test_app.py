
import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def test_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_products_requires_login(client):
    response = client.get("/products")
    assert response.status_code == 302


def test_invalid_page(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
