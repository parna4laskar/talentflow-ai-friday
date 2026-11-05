"""Match-outcome model: P(internal move succeeds) learned from historical placements.

Gradient-boosted trees (scikit-learn) on 10 engineered features. Retrains when
hiring managers record approve/reject feedback (feedback rows are appended as labels).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.core.config import get_settings

FEATURES = ["skill_coverage", "proficiency_gap", "adjacency_score", "same_location", "relocated", "applied_voluntarily",
            "last_rating", "tenure_years", "level_delta", "availability_gap_days"]
_model = None
_lock = threading.Lock()


def _paths():
    d = get_settings().runtime_dir / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d / "outcome_model.joblib", d / "outcome_model_card.json"


def vectorize(f: dict) -> list[float]:
    return [float(f.get(k, 0) or 0) for k in FEATURES]


def train(rows: list[dict]) -> dict:
    """rows: [{"features": {...}, "success": bool}]"""
    X = np.asarray([vectorize(r["features"]) for r in rows])
    y = np.asarray([int(r["success"]) for r in rows])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=7, stratify=y)
    clf = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.06, max_depth=4, l2_regularization=0.5, random_state=7)
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:, 1]
    imp = permutation_importance(clf, Xte, yte, n_repeats=5, random_state=7, scoring="roc_auc")
    card = {
        "model": "HistGradientBoostingClassifier", "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train": int(len(ytr)), "n_test": int(len(yte)), "positive_rate": round(float(y.mean()), 3),
        "auc": round(float(roc_auc_score(yte, proba)), 4), "accuracy": round(float(accuracy_score(yte, proba > 0.5)), 4),
        "feature_importance": sorted(({"feature": f, "importance": round(float(v), 4)} for f, v in zip(FEATURES, imp.importances_mean)),
                                     key=lambda d: -d["importance"]),
        "intended_use": "Advisory signal inside the hybrid match score (15% weight). Never used alone for selection.",
        "excluded_features": ["gender", "age_band", "ethnicity", "name"],
    }
    clf.fit(X, y)  # final model on all data
    mp, cp = _paths()
    joblib.dump(clf, mp)
    cp.write_text(json.dumps(card, indent=2))
    global _model
    with _lock:
        _model = clf
    return card


def model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                mp, _ = _paths()
                _model = joblib.load(mp) if mp.exists() else None
    return _model


def predict(features: list[dict]) -> list[float]:
    m = model()
    if m is None or not features:
        return [0.5] * len(features)
    return [round(float(p), 4) for p in m.predict_proba(np.asarray([vectorize(f) for f in features]))[:, 1]]


def card() -> dict:
    _, cp = _paths()
    return json.loads(cp.read_text()) if cp.exists() else {}
