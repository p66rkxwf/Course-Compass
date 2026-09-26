"""重構 parity：/api/courses/recommend 的輸出必須與重構前（golden）逐筆一致。"""
import json

import pytest

from conftest import FIXTURES
from recommend_cases import CASES

GOLDEN = json.loads((FIXTURES / "recommend_golden.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("idx", range(len(CASES)))
def test_recommend_matches_golden(client, idx):
    case = CASES[idx]
    expected = GOLDEN[idx]
    assert expected["case"] == case

    r = client.post("/api/courses/recommend", json=case)
    assert r.status_code == 200
    courses = r.json()["courses"]
    assert [f"{c['課程代碼']}_{c['序號']}" for c in courses] == expected["keys"]
    assert [c.get("historical_acceptance_rate") for c in courses] == pytest.approx(expected["rates"], nan_ok=True)
