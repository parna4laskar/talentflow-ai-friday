from app.agents.intent import keyword_intent
from app.ml import outcome_model


def test_keyword_intent_fallback_routes_common_questions():
    assert keyword_intent("What is the relocation allowance?").intent == "policy_question"
    assert keyword_intent("Which open roles suit me?").intent == "job_search"
    assert keyword_intent("Who knows Kafka in Pune?").intent == "search_talent"
    assert keyword_intent("Must have: Python. What you will do: build APIs").intent == "match_talent_for_job"


def test_outcome_model_trains_and_predicts_probabilities(tmp_path, monkeypatch):
    import random
    # isolate: never overwrite the production model registry
    monkeypatch.setattr(outcome_model, "_paths", lambda: (tmp_path / "m.joblib", tmp_path / "card.json"))
    monkeypatch.setattr(outcome_model, "_model", None)
    rng = random.Random(1)
    rows = []
    for _ in range(400):
        cov = rng.random()
        rows.append({"features": {"skill_coverage": cov, "last_rating": rng.randint(1, 5)}, "success": cov + rng.gauss(0, 0.2) > 0.5})
    card = outcome_model.train(rows)
    assert card["auc"] > 0.7 and "gender" in card["excluded_features"]
    lo, hi = outcome_model.predict([{"skill_coverage": 0.1, "last_rating": 3}, {"skill_coverage": 0.95, "last_rating": 3}])
    assert 0 <= lo < hi <= 1
