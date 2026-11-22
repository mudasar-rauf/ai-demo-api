from uuid import uuid4

import pytest

NOT_IMPLEMENTED = {"detail": "Not implemented"}


def test_get_task_is_not_implemented(client):
    response = client.get(f"/tasks/{uuid4()}")
    assert response.status_code == 501
    assert response.json() == NOT_IMPLEMENTED


def test_patch_task_is_not_implemented(client):
    response = client.patch(f"/tasks/{uuid4()}", json={"done": True, "due": None})
    assert response.status_code == 501
    assert response.json() == NOT_IMPLEMENTED


def test_delete_task_is_not_implemented(client):
    response = client.delete(f"/tasks/{uuid4()}")
    assert response.status_code == 501
    assert response.json() == NOT_IMPLEMENTED


@pytest.mark.parametrize("field", ["title", "notes", "done"])
def test_patch_refuses_null_for_non_nullable_fields(client, field):
    assert client.patch(f"/tasks/{uuid4()}", json={field: None}).status_code == 422


def test_non_uuid_id_is_rejected(client):
    assert client.get("/tasks/not-a-uuid").status_code == 422
