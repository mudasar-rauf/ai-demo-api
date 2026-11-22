NOT_IMPLEMENTED = {"detail": "Not implemented"}


def test_list_tasks_is_not_implemented(client):
    response = client.get("/tasks", params={"status": "open"})
    assert response.status_code == 501
    assert response.json() == NOT_IMPLEMENTED


def test_list_tasks_rejects_an_unknown_status(client):
    assert client.get("/tasks", params={"status": "later"}).status_code == 422


def test_create_task_is_not_implemented(client):
    response = client.post("/tasks", json={"title": "Buy milk", "due": "2026-11-23"})
    assert response.status_code == 501
    assert response.json() == NOT_IMPLEMENTED


def test_create_task_validates_the_body_first(client):
    assert client.post("/tasks", json={"title": "  "}).status_code == 422
