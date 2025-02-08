from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.test._util.access_token import get_admin_access_token


def test_create_permission():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_permission_data = {
        "name": "new-permission",
        "description": "new-permission-description",
    }
    response = client.post(
        "/api/v1/permissions",
        json=new_permission_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get("id") is not None
    assert response_data.get("id") != ""
    assert response_data.get("name") == "new-permission"
    assert response_data.get("description") == "new-permission-description"


def test_create_permission_bulk():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_first_permission_data = {
        "name": "new-permission-bulk-1",
        "description": "new-permission-bulk-description-1",
    }
    new_second_permission_data = {
        "name": "new-permission-bulk-2",
        "description": "new-permission-bulk-description-2",
    }
    new_permission_data = [new_first_permission_data, new_second_permission_data]
    response = client.post(
        "/api/v1/permissions/bulk",
        json=new_permission_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    # Id should not be empty
    assert response_data[0] is not None
    assert response_data[0] != ""
    assert response_data[1] is not None
    assert response_data[1] != ""
    # Data should match
    assert new_first_permission_data["name"] in [row["name"] for row in response_data]
    assert new_second_permission_data["name"] in [row["name"] for row in response_data]
    assert new_first_permission_data["description"] in [
        row["description"] for row in response_data
    ]
    assert new_second_permission_data["description"] in [
        row["description"] for row in response_data
    ]
