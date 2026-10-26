import copy

from app.services.plan_compiler import SEED, canned_plan, verify_plan


def test_plan_compiler_drops_fabrication_and_keeps_verbatim_doses():
    source = (SEED / "discharge_summary_ramesh.txt").read_text()
    candidate = canned_plan(source, "te")
    fake = copy.deepcopy(candidate["medications"][0])
    fake["name"] = "Fabricated medicine"
    candidate["medications"].append(fake)
    plan, warnings = verify_plan(candidate, source)
    assert len(plan["medications"]) == 5
    assert warnings
    for med in plan["medications"]:
        assert med["dose_text"] in source
        span = med["source_span"]
        assert source[span["start"] : span["end"]] == span["text"]


def test_plan_approval_activation_and_version_gate(seeded_client):
    source = (SEED / "discharge_summary_ramesh.txt").read_text()
    doc = seeded_client.post("/api/v1/patients/P001/documents", json={"text": source}).json()
    response = seeded_client.post(
        "/api/v1/patients/P001/care-plans/draft", json={"document_id": doc["id"]}
    )
    assert response.status_code == 201
    plan = response.json()
    assert len(plan["plan"]["medications"]) == 5
    assert seeded_client.post(f"/api/v1/care-plans/{plan['id']}/activate").status_code == 409
    assert seeded_client.post(f"/api/v1/care-plans/{plan['id']}/approve").status_code == 200
    assert (
        seeded_client.post(f"/api/v1/care-plans/{plan['id']}/activate").json()["status"] == "active"
    )
    edited = seeded_client.patch(
        f"/api/v1/care-plans/{plan['id']}",
        json={"plan": plan["plan"], "expected_version": plan["version"]},
    )
    assert edited.json()["status"] == "draft"
    assert edited.json()["version"] == plan["version"] + 1
    assert seeded_client.post(f"/api/v1/care-plans/{plan['id']}/approve").status_code == 409
