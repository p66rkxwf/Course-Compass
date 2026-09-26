import pandas as pd

from services.predictions import PredictionStore, applicable


def _write_preds(tmp_path):
    pd.DataFrame([{
        "學年度": 114, "學期": 2, "課程代碼": "00227", "序號": 5, "pred_log": 0.5, "q10": 0.1, "q90": 0.9,
        "p_full": 0.8, "est_admit": 0.6, "admit_lo": 0.4, "admit_hi": 0.9, "idx": 29, "model_version": "demand-v1",
    }]).to_csv(tmp_path / "demand_predictions.csv", index=False, encoding="utf-8-sig")


def test_lookup_normalizes_key_types(tmp_path):
    _write_preds(tmp_path)
    store = PredictionStore(tmp_path)
    course = {"學年度": "114", "學期": 2.0, "課程代碼": "00227", "序號": "5", "上限人數": 60, "課程性質": "跨學院通識"}
    pred = store.get(course)
    assert pred["p_full"] == 0.8 and pred["admit_lo"] == 0.4


def test_not_applicable_courses_get_none(tmp_path):
    _write_preds(tmp_path)
    store = PredictionStore(tmp_path)
    base = {"學年度": 114, "學期": 2, "課程代碼": "00227", "序號": 5, "上限人數": 60}
    assert store.get({**base, "課程性質": "自由選修"}) is None
    assert store.get({**base, "課程性質": "系選修", "上限人數": 0}) is None
    assert applicable({**base, "課程性質": "系選修"})


def test_missing_model_dir_is_harmless(tmp_path):
    store = PredictionStore(tmp_path / "nope")
    courses = [{"學年度": 114, "學期": 2, "課程代碼": "X", "序號": 1, "上限人數": 30, "課程性質": "系選修"}]
    store.attach(courses)
    assert courses[0]["admission_pred"] is None
    assert store.meta() == {}
