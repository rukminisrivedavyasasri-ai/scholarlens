import pytest

@pytest.mark.asyncio
async def test_register_and_login_flow(client):
    # 1. Register User
    reg_payload = {
        "email": "dr_vance@university.edu",
        "password": "SecurePassword123!",
        "full_name": "Dr. Evelyn Vance",
        "role": "owner"
    }
    res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "dr_vance@university.edu"
    assert data["user"]["role"] == "owner"
    token = data["access_token"]

    # 2. Get Me with valid token
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "dr_vance@university.edu"

    # 3. Duplicate registration should fail
    dup_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    # 4. Login with correct password
    login_payload = {
        "email": "dr_vance@university.edu",
        "password": "SecurePassword123!"
    }
    login_res = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # 5. Login with invalid password
    bad_login = {
        "email": "dr_vance@university.edu",
        "password": "WrongPassword999!"
    }
    bad_res = await client.post("/api/v1/auth/login", json=bad_login)
    assert bad_res.status_code == 401
