
import pytest
import app as app_module


# --------------------------------------------------
# TEST DATABASE FIXTURE
# --------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):

    # Use a separate temporary database for testing
    test_database = tmp_path / "test_tasks.db"

    monkeypatch.setattr(
        app_module,
        "DATABASE",
        str(test_database)
    )

    # Initialize the test database
    app_module.init_db()

    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as client:
        yield client


# --------------------------------------------------
# HELPER FUNCTION
# --------------------------------------------------

def create_test_task(client):

    client.post("/add", data={
        "title": "Testing Task",
        "description": "Task created for automated testing",
        "priority": "High"
    })

    with app_module.closing(app_module.get_db()) as db:
        task = db.execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT 1"
        ).fetchone()

    return task


# --------------------------------------------------
# BASIC APPLICATION TESTS
# --------------------------------------------------

def test_home_page(client):

    response = client.get("/")

    assert response.status_code == 200


def test_health_endpoint(client):

    response = client.get("/health")

    assert response.status_code == 200


# --------------------------------------------------
# CREATE TASK TEST
# --------------------------------------------------

def test_create_task(client):

    response = client.post("/add", data={
        "title": "New Task",
        "description": "Test task description",
        "priority": "High"
    })

    assert response.status_code == 302

    with app_module.closing(app_module.get_db()) as db:
        task = db.execute(
            "SELECT * FROM tasks WHERE title = ?",
            ("New Task",)
        ).fetchone()

    assert task is not None
    assert task["title"] == "New Task"
    assert task["description"] == "Test task description"
    assert task["priority"] == "High"
    assert task["status"] == "Pending"


# --------------------------------------------------
# READ TASK TEST
# --------------------------------------------------

def test_read_task(client):

    task = create_test_task(client)

    response = client.get("/")

    assert response.status_code == 200
    assert task["title"].encode() in response.data


# --------------------------------------------------
# UPDATE TASK TEST
# --------------------------------------------------

def test_update_task(client):

    task = create_test_task(client)

    response = client.post(
        f"/update/{task['id']}",
        data={
            "title": "Updated Task",
            "description": "Updated description",
            "priority": "Medium"
        }
    )

    assert response.status_code == 302

    updated_task = app_module.get_task(task["id"])

    assert updated_task["title"] == "Updated Task"
    assert updated_task["description"] == "Updated description"
    assert updated_task["priority"] == "Medium"


# --------------------------------------------------
# DELETE TASK TEST
# --------------------------------------------------

def test_delete_task(client):

    task = create_test_task(client)

    response = client.post(
        f"/delete/{task['id']}"
    )

    assert response.status_code == 302

    deleted_task = app_module.get_task(task["id"])

    assert deleted_task is None


# --------------------------------------------------
# COMPLETE TASK TEST
# --------------------------------------------------

def test_complete_task(client):

    task = create_test_task(client)

    response = client.post(
        f"/complete/{task['id']}"
    )

    assert response.status_code == 302

    completed_task = app_module.get_task(task["id"])

    assert completed_task["status"] == "Completed"


# --------------------------------------------------
# REOPEN TASK TEST
# --------------------------------------------------

def test_reopen_task(client):

    task = create_test_task(client)

    # First mark task as completed
    client.post(f"/complete/{task['id']}")

    # Reopen the task
    response = client.post(
        f"/complete/{task['id']}"
    )

    assert response.status_code == 302

    reopened_task = app_module.get_task(task["id"])

    assert reopened_task["status"] == "Pending"


# --------------------------------------------------
# INVALID TASK TEST
# --------------------------------------------------

def test_create_task_without_title(client):

    response = client.post(
        "/add",
        data={
            "title": "",
            "description": "Invalid task",
            "priority": "High"
        }
    )

    assert response.status_code == 302

    with app_module.closing(app_module.get_db()) as db:
        count = db.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

    assert count == 0
