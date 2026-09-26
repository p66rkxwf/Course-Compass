"""防洩漏：第 t 學期的特徵不得依賴第 t 學期（含之後）的登記／選上結果。"""
import numpy as np
import pandas as pd
import pytest

from ml.demand_features import FEATURES, build_course_table, build_features, label_to_idx


@pytest.fixture(scope="module")
def courses(sample_df):
    return build_course_table(sample_df)


@pytest.mark.parametrize("label", ["114-1", "114-2"])
def test_features_ignore_current_and_future_outcomes(courses, label):
    t = label_to_idx(label)
    before = build_features(courses, t)

    tampered = courses.copy()
    rng = np.random.default_rng(0)
    future = tampered["idx"] >= t
    for col in ["登記人數", "選上人數"]:
        tampered.loc[future, col] = rng.integers(0, 500, future.sum())
    # 目標值由登記人數推得，一併重算，模擬「結果完全不同」的平行世界
    cap, reg = tampered["上限人數"], tampered["登記人數"]
    tampered["labeled"] = (cap > 0) & (reg > 0)
    tampered["y_log"] = np.where(tampered["labeled"], np.log(reg.clip(lower=1) / cap.clip(lower=1)), np.nan)
    tampered["y_full"] = np.where(tampered["labeled"], (reg > cap).astype(float), np.nan)

    after = build_features(tampered, t)
    pd.testing.assert_frame_equal(before, after)


def test_features_do_change_when_past_changes(courses):
    """反向檢查：竄改過去學期要能改變特徵，證明上面的測試不是空轉"""
    t = label_to_idx("114-2")
    before = build_features(courses, t)
    tampered = courses.copy()
    past = tampered["idx"] < t
    tampered.loc[past, "y_log"] = tampered.loc[past, "y_log"] + 1.0
    after = build_features(tampered, t)
    assert not before["ct_mean"].equals(after["ct_mean"])


def test_one_row_per_section(courses):
    assert not courses.duplicated(["學年度", "學期", "課程代碼", "序號"]).any()
    assert set(FEATURES).issubset(build_features(courses, label_to_idx("114-2")).columns)
