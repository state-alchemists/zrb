from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.test._util.access_token import get_admin_access_token


def test_read_my_entity_by_id():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_my_entity_data = {
        "my_column": "to-be-read-my-entity",
    }
    insert_response = client.post(
        "/api/v1/my-entities",
        json=new_my_entity_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insert_response.status_code == 200
    id = insert_response.json().get("id")
    # fetching
    response = client.get(
        f"/api/v1/my-entities/{id}", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get("id") == id
    assert response_data.get("my_column") == "to-be-read-my-entity"


def test_read_my_entity_bulk():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_first_my_entity_data = {
        "my_column": "to-be-read-my-entity-bulk-1",
    }
    new_second_my_entity_data = {
        "my_column": "to-be-read-my-entity-bulk-2",
    }
    new_my_entity_data = [new_first_my_entity_data, new_second_my_entity_data]
    insert_response = client.post(
        "/api/v1/my-entities/bulk",
        json=new_my_entity_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insert_response.status_code == 200
    ids = [row["id"] for row in insert_response.json()]
    # fetching
    response = client.get(
        f"/api/v1/my-entities",
        params={
            "filter": "my_column:like:to-be-read-my-entity-bulk-%",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data_count = response.json()["count"]
    assert response_data_count == 2
    response_data = response.json()["data"]
    # Data should match
    assert len([row["id"] for row in response_data if row["id"] in ids]) == 2
    assert new_first_my_entity_data["my_column"] in [
        row["my_column"] for row in response_data
    ]
    assert new_second_my_entity_data["my_column"] in [
        row["my_column"] for row in response_data
    ]
