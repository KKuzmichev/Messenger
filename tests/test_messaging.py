import pytest


@pytest.mark.asyncio
async def test_full_flow(client):
    alice_resp = await client.post("/api/auth/register", json={"username": "alice_e2e", "password": "password123", "display_name": "Alice"})
    alice_token = alice_resp.json()["access_token"]

    bob_resp = await client.post("/api/auth/register", json={"username": "bob_e2e", "password": "password123", "display_name": "Bob"})
    bob_token = bob_resp.json()["access_token"]

    bob_me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {bob_token}"})
    bob_id = bob_me.json()["id"]

    conv_resp = await client.post(
        "/api/conversations",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"type": "direct", "member_ids": [bob_id]},
    )
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    msg_resp = await client.post(
        f"/api/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"ciphertext": "deadbeef", "iv": "01020304", "salt": "05060708", "ephemeral_key": "090a0b0c", "key_id": "1", "attachment_ids": []},
    )
    assert msg_resp.status_code == 201
    assert msg_resp.json()["ciphertext"] == "deadbeef"

    msgs_resp = await client.get(
        f"/api/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert msgs_resp.status_code == 200
    data = msgs_resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["ciphertext"] == "deadbeef"


@pytest.mark.asyncio
async def test_attachment_dedup(client):
    token = (await client.post("/api/auth/register", json={"username": "att_user", "password": "password123", "display_name": "Att"})).json()["access_token"]

    content = b"encrypted file content"
    resp1 = await client.post(
        "/api/attachments",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.txt", content, "text/plain")},
        data={"content_hash": "aabbccdd11223344", "iv": "0102030405060708", "salt": "0807060504030201"},
    )
    assert resp1.status_code == 201
    assert resp1.json()["dedup"] is False
    id1 = resp1.json()["id"]

    resp2 = await client.post(
        "/api/attachments",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.txt", content, "text/plain")},
        data={"content_hash": "aabbccdd11223344", "iv": "0102030405060708", "salt": "0807060504030201"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["dedup"] is True
    assert resp2.json()["id"] == id1
