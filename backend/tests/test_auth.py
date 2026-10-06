from tests.conftest import auth_headers, register_and_login


def test_register_login_me(client):
    token = register_and_login(client, "alice")["access_token"]

    response = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["role"] == "USER"


def test_register_duplicate_username_conflict(client):
    register_and_login(client, "bob")
    response = client.post(
        "/api/v1/auth/register", json={"username": "bob", "password": "secret123"}
    )
    assert response.status_code == 409


def test_login_wrong_password(client):
    register_and_login(client, "carol")
    response = client.post(
        "/api/v1/auth/login", json={"username": "carol", "password": "wrongpass"}
    )
    assert response.status_code == 401


def test_me_requires_auth(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_change_password(client):
    token = register_and_login(client, "dave")["access_token"]
    headers = auth_headers(token)

    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "wrongpass", "new_password": "newpass123"},
        headers=headers,
    )
    assert response.status_code == 400

    response = client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "secret123", "new_password": "newpass123"},
        headers=headers,
    )
    assert response.status_code == 200

    response = client.post(
        "/api/v1/auth/login", json={"username": "dave", "password": "newpass123"}
    )
    assert response.status_code == 200


def test_change_username(client):
    token = register_and_login(client, "erin")["access_token"]
    headers = auth_headers(token)

    response = client.post(
        "/api/v1/auth/me/username",
        json={"current_password": "secret123", "new_username": "erin_new"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["username"] == "erin_new"
