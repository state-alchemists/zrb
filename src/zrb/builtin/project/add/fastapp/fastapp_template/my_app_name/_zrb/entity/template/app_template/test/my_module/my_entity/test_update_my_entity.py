from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.test._util.access_token import get_admin_access_token


def test_update_my_entity():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_my_entity_data = {
        "my_column": "to-be-updated-my-entity",
    }
    insert_response = client.post(
        "/api/v1/my-entities",
        json=new_my_entity_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insert_response.status_code == 200
    id = insert_response.json().get("id")
    # updating
    updated_my_entity_data = {
        "my_column": "updated-my-entity",
    }
    response = client.put(
        f"/api/v1/my-entities/{id}",
        json=updated_my_entity_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get("id") == id
    assert response_data.get("my_column") == "updated-my-entity"


def test_update_my_entity_bulk():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_first_my_entity_data = {
        "my_column": "to-be-updated-my-entity-bulk-1",
    }
    insert_response = client.post(
        "/api/v1/my-entities/bulk",
        json=[new_first_my_entity_data],
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insert_response.status_code == 200
    ids = [row["id"] for row in insert_response.json()]
    # updating (we only test with one data)
    updated_my_entity_data = {"my_column": "updated-my-entity-bulk-1"}
    response = client.put(
        f"/api/v1/my-entities/bulk",
        json={
            "my_entity_ids": ids,
            "data": updated_my_entity_data,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    response_data[0].get("id") == ids[0]
    response_data[0].get("my_column") == updated_my_entity_data["my_column"]
