from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.test._util.access_token import get_admin_access_token


def test_update_permission():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_permission_data = {
        "name": "to-be-updated-permission",
        "description": "to-be-updated-permission-description",
    }
    insert_response = client.post(
        "/api/v1/permissions",
        json=new_permission_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insert_response.status_code == 200
    id = insert_response.json().get("id")
    # updating
    updated_permission_data = {
        "name": "updated-permission",
        "description": "updated-permission-description",
    }
    response = client.put(
        f"/api/v1/permissions/{id}",
        json=updated_permission_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get("id") == id
    assert response_data.get("name") == "updated-permission"
    assert response_data.get("description") == "updated-permission-description"


def test_update_permission_bulk():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_first_permission_data = {
        "name": "to-be-updated-permission-bulk-1",
        "description": "to-be-updated-permission-bulk-description-1",
    }
    insert_response = client.post(
        "/api/v1/permissions/bulk",
        json=[new_first_permission_data],
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insert_response.status_code == 200
    ids = [row["id"] for row in insert_response.json()]
    # updating (we only test with one data)
    updated_permission_data = {"description": "updated-permission-description"}
    response = client.put(
        f"/api/v1/permissions/bulk",
        json={
            "permission_ids": ids,
            "data": updated_permission_data,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    response_data[0].get("id") == ids[0]
    response_data[0].get("name") == new_first_permission_data["name"]
    response_data[0].get("description") == new_first_permission_data["description"]
