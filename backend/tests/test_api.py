import uuid


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_sectors_seeded(client):
    r = await client.get("/api/v1/sectors")
    assert r.status_code == 200
    assert len(r.json()) == 12


async def test_me_requires_auth(client):
    r = await client.get("/api/v1/me")
    assert r.status_code == 401


async def test_me_ok(client, user_token):
    _, token = user_token
    r = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


async def test_google_login_creates_user(client, monkeypatch):
    from app.api.routers import auth as auth_router

    monkeypatch.setattr(
        auth_router,
        "verify_google_id_token",
        lambda token: {"email": "google@example.com", "name": "G", "sub": "g-123", "picture": None},
    )
    r = await client.post("/api/v1/auth/google", json={"id_token": "fake"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "google@example.com"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_api_keys_never_expose_plaintext(client, user_token):
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}
    secret = "sk-super-secret-123"

    r = await client.post(
        "/api/v1/api-keys", headers=headers, json={"provider": "deepseek", "api_key": secret}
    )
    assert r.status_code == 201
    assert secret not in r.text
    assert "key_hint" in r.json()

    r2 = await client.get("/api/v1/api-keys", headers=headers)
    assert r2.status_code == 200
    assert secret not in r2.text


async def test_api_key_upsert_by_provider(client, user_token):
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/api-keys", headers=headers, json={"provider": "openai", "api_key": "sk-first"}
    )
    r = await client.post(
        "/api/v1/api-keys", headers=headers, json={"provider": "openai", "api_key": "sk-second"}
    )
    assert r.status_code == 201
    r2 = await client.get("/api/v1/api-keys", headers=headers)
    providers = [k["provider"] for k in r2.json()]
    assert providers.count("openai") == 1


async def test_questions_seeded(client, user_token):
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.get("/api/v1/questions", headers=headers)
    assert r.status_code == 200
    qs = r.json()
    assert len(qs) >= 21
    assert all(q["is_system"] for q in qs)


async def test_create_and_toggle_question(client, user_token):
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/questions",
        headers=headers,
        json={"criteria": "Margem", "text": "Margem líquida > 10%?", "sector_id": None},
    )
    assert r.status_code == 201
    q = r.json()
    assert q["is_system"] is False

    r = await client.post(
        f"/api/v1/questions/{q['id']}/toggle", headers=headers, json={"enabled": False}
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    r = await client.delete(f"/api/v1/questions/{q['id']}", headers=headers)
    assert r.status_code == 204


async def test_toggle_system_question_keeps_default_visible(client, user_token):
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/v1/questions", headers=headers)
    first = r.json()[0]

    r = await client.post(
        f"/api/v1/questions/{first['id']}/toggle", headers=headers, json={"enabled": False}
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    # "deletar" pergunta padrão == desligar, não remove
    r = await client.delete(f"/api/v1/questions/{first['id']}", headers=headers)
    assert r.status_code == 204

    r = await client.get("/api/v1/questions", headers=headers)
    assert any(q["id"] == first["id"] and q["enabled"] is False for q in r.json())


async def test_chat_requires_api_key(client, user_token):
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/v1/chat", headers=headers, json={"message": "BBAS3"})
    assert r.status_code == 400
    assert "chave" in r.json()["detail"].lower()
