def test_summary_is_not_implemented(client):
    # A 501, not a 422: the path reaches the summary stub, not GET /tasks/{task_id}.
    response = client.get("/tasks/summary")
    assert response.status_code == 501
    assert response.json() == {"detail": "Not implemented"}
