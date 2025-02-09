from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.test._util.access_token import get_admin_access_token


def test_create_my_entity():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_my_entity_data = {
        "my_column": "new-my-entity",
    }
    response = client.post(
        "/api/v1/my-entities",
        json=new_my_entity_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get("id") is not None
    assert response_data.get("id") != ""
    assert response_data.get("my_column") == "new-my-entity"


def test_create_my_entity_bulk():
    client = TestClient(app, base_url="http://localhost")
    access_token = get_admin_access_token()
    new_first_my_entity_data = {
        "my_column": "new-my-entity-bulk-1",
    }
    new_second_my_entity_data = {
        "my_column": "new-my-entity-bulk-2",
    }
    new_my_entity_data = [new_first_my_entity_data, new_second_my_entity_data]
    response = client.post(
        "/api/v1/my-entities/bulk",
        json=new_my_entity_data,
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
    assert new_first_my_entity_data["my_column"] in [
        row["my_column"] for row in response_data
    ]
    assert new_second_my_entity_data["my_column"] in [
        row["my_column"] for row in response_data
    ]
