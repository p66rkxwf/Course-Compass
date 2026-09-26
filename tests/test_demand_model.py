import numpy as np
import pytest

from ml.demand_features import build_course_table, build_features, label_to_idx
from ml.demand_model import DemandModel, _train_calibrated, baseline_predict, evaluate, first_train_idx


@pytest.fixture(scope="module")
def trained(sample_df):
    courses = build_course_table(sample_df)
    first = first_train_idx(courses)
    feats = {t: build_features(courses, t) for t in range(first, int(courses["idx"].max()) + 1)}
    t = label_to_idx("114-2")
    model = _train_calibrated(courses, feats, list(range(first, t)))
    return courses, feats, t, model


def test_prediction_ranges(trained):
    courses, feats, t, model = trained
    p = model.predict(feats[t])
    assert len(p) == len(feats[t])
    assert p["p_full"].between(0, 1).all()
    assert p["est_admit"].between(0, 1).all()
    assert (p["admit_lo"] <= p["admit_hi"] + 1e-12).all()
    assert (p["q10"] <= p["q90"] + 1e-12).all()


def test_model_is_picklable(trained, tmp_path):
    import joblib
    _, feats, t, model = trained
    joblib.dump(model, tmp_path / "m.joblib")
    loaded = joblib.load(tmp_path / "m.joblib")
    np.testing.assert_allclose(loaded.predict(feats[t])["p_full"], model.predict(feats[t])["p_full"])


def test_baseline_only_uses_past(trained):
    courses, _, t, _ = trained
    before = baseline_predict(courses, t, "mean")
    tampered = courses.copy()
    tampered.loc[tampered["idx"] >= t, ["y_log", "y_full", "y_admit"]] = 99.0
    after = baseline_predict(tampered, t, "mean")
    assert before.equals(after)


def test_evaluate_perfect_prediction():
    import pandas as pd
    truth = pd.DataFrame({"y_log": [0.5, -1.0, 0.2], "y_full": [1.0, 0.0, 1.0], "y_admit": [0.6, 1.0, 0.8]})
    pred = pd.DataFrame({"pred_log": [0.5, -1.0, 0.2], "p_full": [1.0, 0.0, 1.0], "est_admit": [0.6, 1.0, 0.8]})
    m = evaluate(truth, pred)
    assert m["mae_log"] == 0 and m["mae_admit"] == 0 and m["brier"] == 0 and m["pr_auc"] == 1
