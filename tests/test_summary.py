from app.models import TaskCreate, TaskUpdate


def _add(store, title, done=False):
    task = store.add(TaskCreate(title=title))
    if done:
        store.update(task.id, TaskUpdate(done=True))
    return task


def test_counts_open_and_done(client, store):
    _add(store, "Buy milk")
    _add(store, "Call the bank")
    _add(store, "Post the letter", done=True)

    response = client.get("/tasks/summary")

    assert response.status_code == 200
    body = response.json()
    assert body == {"total": 3, "open": 2, "done": 1}
    assert body["total"] == body["open"] + body["done"]


def test_counts_every_task_when_all_done(client, store):
    _add(store, "Buy milk", done=True)
    _add(store, "Call the bank", done=True)

    response = client.get("/tasks/summary")

    assert response.status_code == 200
    assert response.json() == {"total": 2, "open": 0, "done": 2}


def test_counts_follow_undone(client, store):
    task = _add(store, "Buy milk", done=True)
    store.update(task.id, TaskUpdate(done=False))

    response = client.get("/tasks/summary")

    assert response.status_code == 200
    assert response.json() == {"total": 1, "open": 1, "done": 0}


def test_empty_store(client):
    response = client.get("/tasks/summary")

    assert response.status_code == 200
    assert response.json() == {"total": 0, "open": 0, "done": 0}


def test_summary_is_not_a_task_id(client):
    # A 200 means the path reached the summary route, not GET /tasks/{task_id},
    # which would answer a 422 (not a UUID) or a 404.
    assert client.get("/tasks/summary").status_code == 200
