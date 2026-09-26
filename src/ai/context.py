"""在 API 之外（評估腳本、測試）建立 CourseContext：直接讀最新 processed 檔與模型檔。"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config import MODELS_DIR, PROCESSED_DATA_DIR
from services.predictions import PredictionStore
from services.recommend import resolve_semester, select_semester

from .tools import CourseContext


def load_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """(API 同款：每門課一列, 原始：每個時段一列)"""
    files = sorted(PROCESSED_DATA_DIR.glob("all_courses_*.csv"))
    if not files:
        raise RuntimeError("找不到 processed 資料，請先執行 python main.py process")
    raw = pd.read_csv(files[-1], encoding="utf-8-sig", low_memory=False)
    dedup = raw.drop_duplicates(subset=["學年度", "學期", "課程代碼", "序號"], keep="last")
    return dedup, raw


def build_context(year: Optional[int] = None, semester: Optional[int] = None,
                  current: Optional[List[Dict[str, Any]]] = None, with_index: bool = True) -> CourseContext:
    dedup, raw = load_frames()
    year, semester = resolve_semester(dedup, year, semester)
    store = PredictionStore(MODELS_DIR)
    index = None
    if with_index:
        try:
            from .index import SyllabusIndex
            index = SyllabusIndex.load(int(year), int(semester))
        except Exception:
            index = None
    return CourseContext(
        semester_df=select_semester(dedup, year, semester), history_df=dedup,
        year=int(year), semester=int(semester), current_courses=current or [],
        predict=lambda c: store.get(c, raw), syllabus_index=index,
    )
