from app.agents import scoring

CAND = {
    "employee_id": "E1", "level": "L3", "city": "Pune", "country": "India", "region": "APAC", "willing_to_relocate": False,
    "relocation_preferences": [], "target_roles": ["Data Engineer"], "open_to_move": True, "last_rating": 4, "tenure_years": 3,
    "availability": {"status": "Rolling off", "available_from": "2026-12-01"},
    "skills": [{"name": "Python", "proficiency": 4, "verified": True}, {"name": "SQL", "proficiency": 2, "verified": False}],
}
JOB = {"level": "L3", "role_family": "Data Engineer", "work_mode": "Hybrid", "relocation_supported": False,
       "location": {"city": "Pune", "country": "India", "region": "APAC"}}
REQ = [{"name": "Python", "min_proficiency": 3, "weight": 1.0}, {"name": "SQL", "min_proficiency": 4, "weight": 1.0},
       {"name": "Apache Spark", "min_proficiency": 3, "weight": 1.0}]


def test_skill_fit_strengths_gaps_and_cap():
    sf = scoring.skill_fit(CAND, REQ, ["Python"])
    assert [s["skill"] for s in sf["strengths"]] == ["Python"]
    assert {g["skill"] for g in sf["gaps"]} == {"SQL", "Apache Spark"}
    assert 0 < sf["score"] <= 0.94  # never perfect while a required skill is short
    assert sf["proficiency_gap"] > 0


def test_adjacency_bridges_missing_skill_via_graph_neighbour():
    gaps = [{"skill": "Apache Spark", "have": 0, "need": 3}]
    adj = scoring.adjacency_score(gaps, {"Apache Spark": {"Python": 0.6}}, {"Python", "SQL"})
    assert adj["bridges"][0]["via"] == "Python" and adj["score"] == 0.6
    assert scoring.adjacency_score([], {}, set())["score"] == 1.0


def test_availability_decays_after_start_date():
    assert scoring.availability_fit(CAND, "2026-12-15")["score"] == 1.0
    late = scoring.availability_fit(CAND, "2026-11-01")
    assert 0 < late["score"] < 1 and late["gap_days"] == 30


def test_location_rules():
    assert scoring.location_fit(CAND, JOB)["score"] == 1.0
    remote_other_region = {**JOB, "work_mode": "Remote", "location": {"city": "London", "country": "UK", "region": "EMEA"}}
    assert scoring.location_fit(CAND, remote_other_region)["score"] == 0.55
    onsite_abroad = {**JOB, "location": {"city": "Austin", "country": "United States", "region": "AMER"}}
    assert scoring.location_fit(CAND, onsite_abroad)["score"] == 0.15


def test_interest_and_combine_and_level_gate():
    assert scoring.interest_signal(CAND, JOB, {"E1"})["score"] == 1.0
    assert scoring.interest_signal(CAND, JOB, set())["score"] == 0.7
    assert scoring.combine({k: 1.0 for k in scoring.WEIGHTS}) == 100.0
    assert abs(sum(scoring.WEIGHTS.values()) - 1.0) < 1e-9
    assert scoring.level_ok(CAND, JOB) and not scoring.level_ok({**CAND, "level": "L1"}, JOB)
