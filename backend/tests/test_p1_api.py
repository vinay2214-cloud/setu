from app.models import metadata, model_for


def test_demo_seed_loads_expected_synthetic_patients_and_alerts(seeded_client):
    login = seeded_client.post(
        "/api/v1/auth/login", json={"email": "dr.anitha@demo.setu", "password": "demo123"}
    )
    assert login.status_code == 200
    patients = seeded_client.get("/api/v1/patients")
    assert len(patients.json()["items"]) == 5
    assert model_for("patients").__name__ == "Patients"
    assert len(metadata.tables) == 16
    alerts = seeded_client.get("/api/v1/alerts")
    assert {(item["patient"]["id"], item["rule"]["id"]) for item in alerts.json()["items"]} == {
        ("P002", "R-ADH-01"),
        ("P003", "R-QUESTION-01"),
        ("P005", "R-NORESP-01"),
    }


def test_rule_evaluate_returns_hero_rules_and_actions_are_audited(seeded_client):
    seeded_client.post(
        "/api/v1/auth/login",
        json={"email": "dr.anitha@demo.setu", "password": "demo123"},
    )
    facts = {
        "conditions": ["diabetes", "hypertension"],
        "days_since_discharge": 8,
        "max_missed_streak_critical": 2,
        "symptoms": ["leg_swelling"],
        "symptom_severity_unknown_critical": False,
        "glucose_latest": None,
        "glucose_context": None,
        "bp_sys_latest": None,
        "bp_dia_latest": None,
        "consecutive_no_response": 0,
        "intent_confidence_min": 1.0,
        "needs_human": False,
        "medical_question": False,
    }
    evaluated = seeded_client.post("/api/v1/rules/evaluate", json={"facts": facts})
    assert {rule["id"] for rule in evaluated.json()["fired"]} == {"R-ADH-01", "R-COMBO-01"}

    alert_id = seeded_client.get("/api/v1/alerts").json()["items"][0]["id"]
    approved = seeded_client.post(
        f"/api/v1/alerts/{alert_id}/approve-call", json={"assignee": "dr.anitha"}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "acknowledged"
    assert any(event["action"] == "call_approved" for event in approved.json()["events"])


def test_resolve_requires_a_note(seeded_client):
    seeded_client.post(
        "/api/v1/auth/login",
        json={"email": "dr.anitha@demo.setu", "password": "demo123"},
    )
    alert_id = seeded_client.get("/api/v1/alerts").json()["items"][0]["id"]
    response = seeded_client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"note": "  "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["request_id"].startswith("req_")


def test_demo_mutations_require_auth_and_lists_page(seeded_client):
    seeded_client.post("/api/v1/auth/logout")
    denied = seeded_client.post("/api/v1/demo/reset")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "unauthorized"
    login = seeded_client.post(
        "/api/v1/auth/login", json={"email": "dr.anitha@demo.setu", "password": "demo123"}
    )
    assert login.status_code == 200
    first_page = seeded_client.get("/api/v1/patients?limit=2").json()
    assert len(first_page["items"]) == 2
    assert first_page["next_cursor"]
    second_page = seeded_client.get(
        f"/api/v1/patients?limit=2&cursor={first_page['next_cursor']}"
    ).json()
    assert len(second_page["items"]) == 2
    assert not ({p["id"] for p in first_page["items"]} & {p["id"] for p in second_page["items"]})
    malformed = seeded_client.get("/api/v1/patients?cursor=not-a-cursor")
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "validation_error"
