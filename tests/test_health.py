from app.main import app

WEB_APP_ORIGIN = "http://localhost:3000"


def test_health_answers_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_declares_the_seven_endpoints():
    paths = app.openapi()["paths"]
    declared = {(method.upper(), path) for path, ops in paths.items() for method in ops}
    assert declared == {
        ("GET", "/health"),
        ("GET", "/tasks"),
        ("POST", "/tasks"),
        ("GET", "/tasks/summary"),
        ("GET", "/tasks/{task_id}"),
        ("PATCH", "/tasks/{task_id}"),
        ("DELETE", "/tasks/{task_id}"),
    }


def test_openapi_declares_the_success_codes():
    paths = app.openapi()["paths"]
    assert "201" in paths["/tasks"]["post"]["responses"]
    assert "204" in paths["/tasks/{task_id}"]["delete"]["responses"]


def test_cors_allows_the_web_app(client):
    response = client.options(
        "/tasks",
        headers={"Origin": WEB_APP_ORIGIN, "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == WEB_APP_ORIGIN


def test_cors_refuses_other_origins(client):
    response = client.options(
        "/tasks",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_header_on_a_simple_request(client):
    response = client.get("/health", headers={"Origin": WEB_APP_ORIGIN})
    assert response.headers["access-control-allow-origin"] == WEB_APP_ORIGIN
