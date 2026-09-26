import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def sample_df() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "courses_sample.csv", encoding="utf-8-sig", low_memory=False)


@pytest.fixture
def client(sample_df, monkeypatch):
    """以固定樣本資料取代最新 processed 檔的 API client"""
    from fastapi.testclient import TestClient
    import api.app as app_module

    from services.predictions import PredictionStore

    app_module._courses_cache.clear()
    app_module._courses_cache["latest"] = sample_df.copy()
    app_module._courses_cache["raw"] = sample_df.copy()
    # 測試不讀真正的模型檔：指向空資料夾，預測一律為 None
    monkeypatch.setattr(app_module, "prediction_store", PredictionStore(Path(__file__).parent / "fixtures" / "no_models"))
    yield TestClient(app_module.app)
    app_module._courses_cache.clear()
