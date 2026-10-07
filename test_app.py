"""
test_app.py — Pytest suite for ACEest Fitness & Gym.

Coverage target: 90%+ across core.py, db.py, report.py, app.py.

Strategy:
    - Each test gets an isolated temp SQLite DB (via monkeypatch)
    - Flask test_client() used for route tests (no real server needed)
    - Pure functions in core.py tested with parametrize
    - PDF bytes validated by magic-number prefix (%PDF-)
"""

import pytest

import core
import db
from app import app
from report import build_client_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """
    Redirect db.DB_PATH to a fresh temp DB for every test.
    Ensures tests don't pollute the real aceest_fitness.db.
    """
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(test_db))
    db.init_db()
    yield
    # tmp_path is auto-cleaned by pytest


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_client_payload():
    """Reusable client payload for tests."""
    return {
        "name": "Alice",
        "age": 28,
        "height": 170,
        "weight": 65,
        "program": "Fat Loss (FL) - 3 day",
        "target_weight": 60,
        "target_adherence": 80,
    }


# ===========================================================================
# core.py — business logic
# ===========================================================================

@pytest.mark.parametrize(
    "weight,program,expected",
    [
        (65, "Fat Loss (FL) - 3 day", 1430),
        (65, "Fat Loss (FL) - 5 day", 1560),
        (65, "Muscle Gain (MG) - PPL", 2275),
        (60, "Beginner (BG)", 1560),
        (80, "Beginner (BG)", 2080),
    ],
)
def test_calculate_calories(weight, program, expected):
    assert core.calculate_calories(weight, program) == expected


def test_calculate_calories_invalid_weight():
    with pytest.raises(ValueError, match="positive"):
        core.calculate_calories(0, "Beginner (BG)")
    with pytest.raises(ValueError, match="positive"):
        core.calculate_calories(-10, "Beginner (BG)")


def test_calculate_calories_unknown_program():
    with pytest.raises(ValueError, match="Unknown program"):
        core.calculate_calories(70, "Nonexistent Program")


@pytest.mark.parametrize(
    "weight,height,expected",
    [
        (70, 175, 22.9),
        (90, 180, 27.8),
        (50, 160, 19.5),
        (100, 190, 27.7),
    ],
)
def test_calculate_bmi(weight, height, expected):
    assert core.calculate_bmi(weight, height) == expected


def test_calculate_bmi_invalid():
    with pytest.raises(ValueError):
        core.calculate_bmi(0, 175)
    with pytest.raises(ValueError):
        core.calculate_bmi(70, 0)
    with pytest.raises(ValueError):
        core.calculate_bmi(-5, 175)


@pytest.mark.parametrize(
    "bmi,expected_category",
    [
        (17.0, "Underweight"),
        (18.4, "Underweight"),
        (18.5, "Normal"),
        (24.9, "Normal"),
        (25.0, "Overweight"),
        (29.9, "Overweight"),
        (30.0, "Obese"),
        (45.0, "Obese"),
    ],
)
def test_bmi_category(bmi, expected_category):
    result = core.bmi_category(bmi)
    assert result["category"] == expected_category
    assert "risk" in result
    assert len(result["risk"]) > 10  # non-trivial risk text


def test_list_programs():
    programs = core.list_programs()
    assert isinstance(programs, list)
    assert len(programs) == 4
    for p in programs:
        assert {"name", "factor", "desc"}.issubset(p.keys())


# ===========================================================================
# db.py — persistence layer
# ===========================================================================

def test_upsert_and_get_client():
    c = db.upsert_client({"name": "Bob", "age": 30, "weight": 80})
    assert c["name"] == "Bob"
    assert c["age"] == 30

    fetched = db.get_client("Bob")
    assert fetched is not None
    assert fetched["weight"] == 80


def test_upsert_updates_existing_client():
    db.upsert_client({"name": "Carol", "age": 25})
    db.upsert_client({"name": "Carol", "age": 26, "weight": 55})
    fetched = db.get_client("Carol")
    assert fetched["age"] == 26
    assert fetched["weight"] == 55


def test_get_client_missing_returns_none():
    assert db.get_client("Ghost") is None


def test_list_clients_empty():
    assert db.list_clients() == []


def test_list_clients_ordered():
    db.upsert_client({"name": "Zara"})
    db.upsert_client({"name": "Alice"})
    db.upsert_client({"name": "Mike"})
    names = [c["name"] for c in db.list_clients()]
    assert names == ["Alice", "Mike", "Zara"]


def test_delete_client():
    db.upsert_client({"name": "Temp"})
    assert db.delete_client("Temp") is True
    assert db.get_client("Temp") is None
    assert db.delete_client("Temp") is False  # second delete → False


def test_log_progress_and_get():
    db.upsert_client({"name": "Dave"})
    entry = db.log_progress("Dave", "Week 01 - 2026", 75)
    assert entry["adherence"] == 75

    history = db.get_progress("Dave")
    assert len(history) == 1
    assert history[0]["week"] == "Week 01 - 2026"


def test_log_progress_rejects_out_of_range():
    with pytest.raises(ValueError):
        db.log_progress("X", "W1", -1)
    with pytest.raises(ValueError):
        db.log_progress("X", "W1", 101)


def test_log_workout_and_get():
    db.upsert_client({"name": "Eve"})
    db.log_workout("Eve", "2026-10-06", "Strength", 60, "Felt good")
    workouts = db.get_workouts("Eve")
    assert len(workouts) == 1
    assert workouts[0]["workout_type"] == "Strength"
    assert workouts[0]["duration_min"] == 60


# ===========================================================================
# report.py — PDF generation
# ===========================================================================

def test_build_client_report_minimal():
    pdf = build_client_report({"name": "Test"})
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500


def test_build_client_report_full(sample_client_payload):
    progress = [
        {"week": "Week 01 - 2026", "adherence": 70},
        {"week": "Week 02 - 2026", "adherence": 85},
    ]
    pdf = build_client_report(sample_client_payload, progress)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_build_client_report_handles_missing_fields():
    """Sparse data must not crash."""
    pdf = build_client_report({})
    assert pdf.startswith(b"%PDF-")


# ===========================================================================
# app.py — HTTP routes
# ===========================================================================

def test_home(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.get_json()
    assert data["service"].startswith("ACEest")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "healthy"


def test_programs_endpoint(client):
    r = client.get("/programs")
    assert r.status_code == 200
    assert len(r.get_json()) == 4


def test_calories_endpoint(client):
    r = client.post(
        "/calculate/calories",
        json={"weight": 65, "program": "Fat Loss (FL) - 3 day"},
    )
    assert r.status_code == 200
    assert r.get_json()["calories"] == 1430


def test_calories_endpoint_missing_field(client):
    r = client.post("/calculate/calories", json={"weight": 65})
    assert r.status_code == 400
    assert "Missing field" in r.get_json()["error"]


def test_calories_endpoint_bad_program(client):
    r = client.post(
        "/calculate/calories",
        json={"weight": 65, "program": "Fake"},
    )
    assert r.status_code == 400


def test_bmi_endpoint(client):
    r = client.post("/calculate/bmi", json={"weight": 70, "height": 175})
    assert r.status_code == 200
    data = r.get_json()
    assert data["bmi"] == 22.9
    assert data["category"] == "Normal"


def test_bmi_endpoint_bad_input(client):
    r = client.post("/calculate/bmi", json={"weight": "abc", "height": 175})
    assert r.status_code == 400


def test_create_client_auto_calculates_calories(client, sample_client_payload):
    r = client.post("/clients", json=sample_client_payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == "Alice"
    assert data["calories"] == 1430  # 65 * 22


def test_create_client_missing_name(client):
    r = client.post("/clients", json={"program": "Beginner (BG)"})
    assert r.status_code == 400


def test_create_client_missing_program(client):
    r = client.post("/clients", json={"name": "X"})
    assert r.status_code == 400


def test_list_clients_endpoint(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    client.post("/clients", json={**sample_client_payload, "name": "Bob"})

    r = client.get("/clients")
    assert r.status_code == 200
    assert len(r.get_json()) == 2


def test_get_client_endpoint(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    r = client.get("/clients/Alice")
    assert r.status_code == 200
    assert r.get_json()["name"] == "Alice"


def test_get_client_404(client):
    r = client.get("/clients/Ghost")
    assert r.status_code == 404


def test_delete_client_endpoint(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    r = client.delete("/clients/Alice")
    assert r.status_code == 200
    assert r.get_json()["status"] == "deleted"

    r2 = client.delete("/clients/Alice")
    assert r2.status_code == 404


def test_log_progress_endpoint(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    r = client.post(
        "/clients/Alice/progress",
        json={"week": "Week 01 - 2026", "adherence": 75},
    )
    assert r.status_code == 201
    assert r.get_json()["adherence"] == 75


def test_log_progress_requires_client(client):
    r = client.post(
        "/clients/Ghost/progress",
        json={"adherence": 75},
    )
    assert r.status_code == 404


def test_log_progress_invalid_adherence(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    r = client.post("/clients/Alice/progress", json={"adherence": "bad"})
    assert r.status_code == 400

    r2 = client.post("/clients/Alice/progress", json={"adherence": 150})
    assert r2.status_code == 400


def test_get_progress_endpoint(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    client.post(
        "/clients/Alice/progress",
        json={"week": "Week 01 - 2026", "adherence": 80},
    )
    r = client.get("/clients/Alice/progress")
    assert r.status_code == 200
    assert len(r.get_json()) == 1


def test_pdf_report_endpoint(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    client.post(
        "/clients/Alice/progress",
        json={"week": "Week 01 - 2026", "adherence": 70},
    )
    r = client.get("/clients/Alice/report.pdf")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/pdf"
    assert r.data.startswith(b"%PDF-")


def test_pdf_report_download_flag(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    r = client.get("/clients/Alice/report.pdf?download=1")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")


def test_pdf_report_client_not_found(client):
    r = client.get("/clients/Ghost/report.pdf")
    assert r.status_code == 404


def test_demo_endpoint(client, sample_client_payload):
    client.post("/clients", json=sample_client_payload)
    r = client.get("/demo/Alice")
    assert r.status_code == 200
    assert b"ACEest Report Preview" in r.data