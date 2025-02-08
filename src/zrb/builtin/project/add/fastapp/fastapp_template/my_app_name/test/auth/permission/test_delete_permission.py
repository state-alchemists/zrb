from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.test._util.access_token import get_admin_access_token


def test_delete_permission():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_permission_data = {
        "name": "to-be-deleted-permission",
        "description": "to-be-deleted-permission-description",
    }
    insert_response = client.post(
        "/api/v1/permissions",
        json=new_permission_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insert_response.status_code == 200
    id = insert_response.json().get("id")
    # deleting
    response = client.delete(
        f"/api/v1/permissions/{id}", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get("id") == id
    assert response_data.get("name") == "to-be-deleted-permission"
    assert response_data.get("description") == "to-be-deleted-permission-description"


def test_delete_permission_bulk():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_first_permission_data = {
        "name": "to-be-deleted-permission-bulk-1",
        "description": "to-be-deleted-permission-bulk-description-1",
    }
    new_second_permission_data = {
        "name": "to-be-deleted-permission-bulk-2",
        "description": "to-be-deleted-permission-bulk-description-2",
    }
    new_permission_data = [new_first_permission_data, new_second_permission_data]
    insert_response = client.post(
        "/api/v1/permissions/bulk",
        json=new_permission_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insert_response.status_code == 200
    ids = [row["id"] for row in insert_response.json()]
    # deleting (use client.request since client.delete doesn't support json param)
    response = client.request(
        "DELETE",
        f"/api/v1/permissions/bulk",
        json=ids,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    # Data should match
    assert len([row["id"] for row in response_data if row["id"] in ids]) == 2
    assert new_first_permission_data["name"] in [row["name"] for row in response_data]
    assert new_second_permission_data["name"] in [row["name"] for row in response_data]
    assert new_first_permission_data["description"] in [
        row["description"] for row in response_data
    ]
    assert new_second_permission_data["description"] in [
        row["description"] for row in response_data
    ]
