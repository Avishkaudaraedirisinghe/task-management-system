
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    render_template,
    flash,
    jsonify
)

# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "development-secret-key-change-in-production"
)

DATABASE = os.environ.get("TASKS_DATABASE", "tasks.db")

MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 500

VALID_PRIORITIES = ("Low", "Medium", "High")
VALID_STATUSES = ("Pending", "Completed")


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db():
    """Create and return a SQLite database connection."""

    db = sqlite3.connect(DATABASE, timeout=10)
    db.row_factory = sqlite3.Row

    return db


def init_db():
    """Create the tasks table if it does not exist."""

    with closing(get_db()) as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'Medium',
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        db.commit()


def get_current_time():
    """Return the current UTC time as an ISO formatted string."""

    return datetime.now(timezone.utc).isoformat()


def get_task(task_id):
    """Retrieve a single task using its ID."""

    with closing(get_db()) as db:

        task = db.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

    return task


# --------------------------------------------------
# TASK VALIDATION
# --------------------------------------------------

def validate_task(title, description, priority):
    """Validate task input before saving it."""

    errors = []

    title = title.strip()
    description = description.strip()

    if not title:
        errors.append("Task title is required.")

    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(
            f"Task title cannot exceed {MAX_TITLE_LENGTH} characters."
        )

    if len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append(
            f"Description cannot exceed {MAX_DESCRIPTION_LENGTH} characters."
        )

    if priority not in VALID_PRIORITIES:
        errors.append("Please select a valid priority.")

    return errors


# --------------------------------------------------
# HOME - VIEW AND SEARCH TASKS
# --------------------------------------------------

@app.route("/")
def home():

    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "All")

    query = "SELECT * FROM tasks WHERE 1=1"
    parameters = []

    if search_query:
        query += " AND title LIKE ?"
        parameters.append(f"%{search_query}%")

    if status_filter in VALID_STATUSES:
        query += " AND status = ?"
        parameters.append(status_filter)

    query += """
        ORDER BY
            CASE priority
                WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2
                WHEN 'Low' THEN 3
            END,
            id DESC
    """

    with closing(get_db()) as db:

        tasks = db.execute(
            query,
            parameters
        ).fetchall()

        total_tasks = db.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

        completed_tasks = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'Completed'"
        ).fetchone()[0]

        pending_tasks = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'Pending'"
        ).fetchone()[0]

    return render_template(
        "index.html",
        tasks=tasks,
        search_query=search_query,
        status_filter=status_filter,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks
    )


# --------------------------------------------------
# CREATE TASK
# --------------------------------------------------

@app.route("/add", methods=["POST"])
def add_task():

    title = request.form.get("title", "")
    description = request.form.get("description", "")
    priority = request.form.get("priority", "Medium")

    errors = validate_task(title, description, priority)

    if errors:
        for error in errors:
            flash(error, "error")

        return redirect(url_for("home"))

    current_time = get_current_time()

    with closing(get_db()) as db:

        db.execute("""
            INSERT INTO tasks (
                title,
                description,
                priority,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            title.strip(),
            description.strip(),
            priority,
            "Pending",
            current_time,
            current_time
        ))

        db.commit()

    flash("Task created successfully!", "success")

    return redirect(url_for("home"))


# --------------------------------------------------
# UPDATE TASK
# --------------------------------------------------

@app.route("/update/<int:task_id>", methods=["POST"])
def update_task(task_id):

    task = get_task(task_id)

    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("home"))

    title = request.form.get("title", "")
    description = request.form.get(
        "description",
        task["description"]
    )
    priority = request.form.get(
        "priority",
        task["priority"]
    )

    errors = validate_task(title, description, priority)

    if errors:
        for error in errors:
            flash(error, "error")

        return redirect(url_for("home"))

    with closing(get_db()) as db:

        db.execute("""
            UPDATE tasks
            SET title = ?,
                description = ?,
                priority = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            title.strip(),
            description.strip(),
            priority,
            get_current_time(),
            task_id
        ))

        db.commit()

    flash("Task updated successfully!", "success")

    return redirect(url_for("home"))


# --------------------------------------------------
# COMPLETE / REOPEN TASK
# --------------------------------------------------

@app.route("/complete/<int:task_id>", methods=["POST"])
def complete_task(task_id):

    task = get_task(task_id)

    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("home"))

    new_status = (
        "Pending"
        if task["status"] == "Completed"
        else "Completed"
    )

    with closing(get_db()) as db:

        db.execute("""
            UPDATE tasks
            SET status = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            new_status,
            get_current_time(),
            task_id
        ))

        db.commit()

    flash(
        f"Task marked as {new_status.lower()}!",
        "success"
    )

    return redirect(url_for("home"))


# --------------------------------------------------
# DELETE TASK
# --------------------------------------------------

@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):

    with closing(get_db()) as db:

        cursor = db.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,)
        )

        db.commit()

        deleted = cursor.rowcount

    if deleted:
        flash("Task deleted successfully!", "success")
    else:
        flash("Task not found.", "error")

    return redirect(url_for("home"))


# --------------------------------------------------
# HEALTH CHECK - FOR JENKINS / DEPLOYMENT
# --------------------------------------------------

@app.route("/health", methods=["GET"])
def health_check():

    try:
        with closing(get_db()) as db:
            db.execute("SELECT 1")

        return jsonify({
            "status": "healthy",
            "application": "Task Management System",
            "database": "connected"
        }), 200

    except sqlite3.Error:

        return jsonify({
            "status": "unhealthy",
            "application": "Task Management System",
            "database": "disconnected"
        }), 500


# --------------------------------------------------
# ERROR HANDLING
# --------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "index.html",
        tasks=[],
        search_query="",
        status_filter="All",
        total_tasks=0,
        completed_tasks=0,
        pending_tasks=0
    ), 404


@app.errorhandler(500)
def internal_server_error(error):

    return jsonify({
        "error": "Internal Server Error",
        "message": "Something went wrong. Please try again later."
    }), 500


# --------------------------------------------------
# APPLICATION INITIALIZATION
# --------------------------------------------------

# Initialize database when the application is loaded.
# This also supports Gunicorn deployment.

init_db()


# --------------------------------------------------
# DEVELOPMENT SERVER
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
