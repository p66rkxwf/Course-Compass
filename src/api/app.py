from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from config import PROCESSED_DATA_DIR, WEB_DIR, API_HOST, API_PORT, LOG_LEVEL, LOG_FORMAT, LOG_FILE, LOG_DIR, MODELS_DIR
from utils.common import safe_read_csv, setup_logging
from services.recommend import (
    clean_course_data, clean_single_course, calculate_historical_stats, attach_historical_rates,
    resolve_semester, select_semester, filter_courses,
)
from services.predictions import PredictionStore

prediction_store = PredictionStore(MODELS_DIR)


app = FastAPI(title="Course Master API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/css", StaticFiles(directory=str(WEB_DIR / "assets" / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(WEB_DIR / "assets" / "js")), name="js")
app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")

_courses_cache: Dict[str, pd.DataFrame] = {}

def get_latest_courses_df() -> Optional[pd.DataFrame]:
    """取得最新課程資料"""
    cache_key = "latest"
    if cache_key in _courses_cache:
        return _courses_cache[cache_key]
    
    processed_files = sorted(PROCESSED_DATA_DIR.glob("all_courses_*.csv"))
    if not processed_files:
        return None
    
    latest_file = processed_files[-1]
    df = safe_read_csv(latest_file)
    
    if df is not None:
        if '課程代碼' in df.columns and '序號' in df.columns:
            subset = [c for c in ['學年度', '學期', '課程代碼', '序號'] if c in df.columns]
            df = df.drop_duplicates(subset=subset, keep='last')
        _courses_cache[cache_key] = df
        
    return df

def get_raw_courses_df() -> Optional[pd.DataFrame]:
    """未去重的 processed 資料（一個上課時段一列）；中籤預測現算特徵時需要完整時段資訊"""
    if "raw" in _courses_cache:
        return _courses_cache["raw"]
    processed_files = sorted(PROCESSED_DATA_DIR.glob("all_courses_*.csv"))
    if not processed_files:
        return None
    df = safe_read_csv(processed_files[-1])
    if df is not None:
        _courses_cache["raw"] = df
    return df

def attach_predictions(courses: List[Dict[str, Any]]) -> None:
    prediction_store.attach(courses, get_raw_courses_df())

def get_all_historical_courses_df() -> Optional[pd.DataFrame]:
    """取得所有歷史課程資料"""
    return get_latest_courses_df()

def get_courses_by_semester(year: int, semester: int) -> Optional[pd.DataFrame]:
    cache_key = f"{year}_{semester}"
    if cache_key in _courses_cache:
        return _courses_cache[cache_key]
    
    df = get_all_historical_courses_df()
    if df is None:
        return None
    
    filtered = df[
        (df['學年度'].astype(str) == str(year)) & 
        (df['學期'].astype(str) == str(semester))
    ].copy()
    
    if not filtered.empty:
        _courses_cache[cache_key] = filtered
    return filtered

class CourseSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 50

class CourseResponse(BaseModel):
    courses: List[Dict[str, Any]]
    total: int

class RecommendRequest(BaseModel):
    empty_slots: Optional[List[Dict[str, int]]] = None
    target_credits: int = 20
    category: Optional[str] = None 
    college: Optional[str] = None
    department: Optional[str] = None
    grade: Optional[str] = None
    level: Optional[str] = None
    current_courses: List[Dict[str, Any]] = []
    year: Optional[int] = None
    semester: Optional[int] = None
    preferred_days: Optional[List[str]] = None

@app.get("/")
async def read_root():
    return FileResponse(WEB_DIR / "index.html")

@app.get("/api/courses/all")
async def get_all_courses(year: Optional[int] = None, semester: Optional[int] = None):
    try:
        if year and semester:
            df = get_courses_by_semester(year, semester)
        else:
            df = get_latest_courses_df()
        
        if df is None or df.empty:
            return CourseResponse(courses=[], total=0)
        
        courses = df.to_dict('records')
        courses = clean_course_data(courses)
        return CourseResponse(courses=courses, total=len(courses))
    except Exception as e:
        logging.error(f"獲取課程列表失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取課程列表失敗")

@app.get("/api/courses/search")
async def search_courses(q: str, limit: int = 50):
    try:
        latest_df = get_latest_courses_df()
        if latest_df is None or latest_df.empty:
            raise HTTPException(status_code=404, detail="沒有處理過的課程數據")

        query = q.lower()
        mask = (
            latest_df['課程名稱'].astype(str).str.lower().str.contains(query, na=False) |
            latest_df['教師姓名'].astype(str).str.lower().str.contains(query, na=False) |
            latest_df['英文課程名稱'].astype(str).str.lower().str.contains(query, na=False)
        )
        results = latest_df[mask].head(limit)
        history_df = get_all_historical_courses_df()
        stats_map = calculate_historical_stats(history_df)
        courses = results.to_dict('records')
        courses = clean_course_data(courses)

        attach_historical_rates(courses, stats_map)
        attach_predictions(courses)

        return CourseResponse(courses=courses, total=len(courses))
    except Exception as e:
        logging.error(f"搜索課程失敗: {e}")
        raise HTTPException(status_code=500, detail="搜索失敗")

@app.get("/api/courses/by-class")
async def get_courses_by_class(department: str, class_name: str, year: int, semester: int):
    try:
        df = get_courses_by_semester(year, semester)
        if df is None or df.empty:
            return CourseResponse(courses=[], total=0)
        
        mask = (
            (df['開課班別(代表)'].astype(str).str.contains(department, na=False)) |
            (df['開課班別(代表)'].astype(str).str.contains(class_name, na=False))
        )
        required_mask = df['課程性質'].astype(str).str.contains('必修', na=False)
        required_courses = df[mask & required_mask]
        elective_courses = df[mask & ~required_mask]
        result_df = pd.concat([required_courses, elective_courses], ignore_index=True)
        courses = result_df.to_dict('records')
        courses = clean_course_data(courses)
        return CourseResponse(courses=courses, total=len(courses))
    except Exception as e:
        logging.error(f"獲取班級課程失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取班級課程失敗")

@app.post("/api/courses/recommend")
async def recommend_courses(request: RecommendRequest):
    try:
        full_df = get_latest_courses_df() 
        if full_df is None or full_df.empty:
            raise HTTPException(status_code=404, detail="沒有處理過的課程數據")
        
        current_year, current_semester = resolve_semester(full_df, request.year, request.semester)
        target_df = select_semester(full_df, current_year, current_semester)
        if target_df.empty:
            return CourseResponse(courses=[], total=0)
        
        filtered = filter_courses(
            target_df,
            category=request.category,
            college=request.college,
            department=request.department,
            grade=request.grade,
            level=request.level,
            preferred_days=request.preferred_days,
            current_courses=request.current_courses,
            empty_slots=request.empty_slots,
        )

        history_df = get_all_historical_courses_df()
        stats_map = calculate_historical_stats(history_df)

        results_list = filtered.head(50).to_dict('records')
        results_list = clean_course_data(results_list)
        attach_historical_rates(results_list, stats_map)
        attach_predictions(results_list)

        return CourseResponse(courses=results_list, total=len(results_list))
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"推薦 API 錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"系統錯誤: {str(e)}")

@app.get("/api/courses/history")
async def get_course_history(q: str, limit: int = 100):
    try:
        df = get_all_historical_courses_df()
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="沒有處理過的課程數據")
        
        query = q.lower()
        mask = (
            df['課程名稱'].astype(str).str.lower().str.contains(query, na=False) |
            df['教師姓名'].astype(str).str.lower().str.contains(query, na=False)
        )
        results = df[mask].sort_values(['學年度', '學期'], ascending=[False, False]).head(limit)
        courses = results.to_dict('records')
        courses = clean_course_data(courses)
        attach_predictions(courses)
        return CourseResponse(courses=courses, total=len(courses))
    except Exception as e:
        raise HTTPException(status_code=500, detail="獲取歷年資料失敗")

@app.get("/api/courses/stats")
async def get_course_stats():
    try:
        df = get_latest_courses_df()
        if df is None or df.empty:
             raise HTTPException(status_code=404)
        stats = {
            "total_courses": len(df),
            "total_teachers": df['教師姓名'].nunique() if '教師姓名' in df.columns else 0,
            "departments": df['開課班別(代表)'].value_counts().head(10).to_dict() if '開課班別(代表)' in df.columns else {},
            "course_types": df['課程性質'].value_counts().to_dict() if '課程性質' in df.columns else {},
            "english_only": int(df['全英語授課'].sum()) if '全英語授課' in df.columns else 0,
            "avg_enrollment": float(df['選上人數'].mean()) if '選上人數' in df.columns else 0,
            "max_enrollment": int(df['選上人數'].max()) if '選上人數' in df.columns else 0
        }
        return stats
    except: raise HTTPException(500)

@app.get("/api/predict/model-info")
async def get_prediction_model_info():
    """中籤預測模型的版本、訓練資料與驗證結果（開發折＋held-out），供介面說明用"""
    meta = prediction_store.meta()
    if not meta:
        raise HTTPException(status_code=404, detail="尚未訓練中籤預測模型")
    keys = ["model_version", "trained_at", "data_file", "frozen_train_semesters", "holdout_semester",
            "dev_test_semesters", "dev_summary", "holdout"]
    return {k: meta.get(k) for k in keys}

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    current_courses: List[Dict[str, Any]] = []
    year: Optional[int] = None
    semester: Optional[int] = None
    provider: Optional[str] = None  # "mock" 可強制使用離線規則模式

_syllabus_indexes: Dict[tuple, Any] = {}

def get_syllabus_index(year: int, semester: int):
    """教學大綱向量索引（python main.py build-index 產生）；沒有就回傳 None，助理會略過大綱搜尋"""
    key = (year, semester)
    if key not in _syllabus_indexes:
        try:
            from ai.index import SyllabusIndex
            _syllabus_indexes[key] = SyllabusIndex.load(year, semester)
        except Exception as e:
            logging.info(f"{year}-{semester} 沒有可用的大綱索引：{e}")
            _syllabus_indexes[key] = None
    return _syllabus_indexes[key]

@app.on_event("startup")
def warm_up_syllabus_index():
    """啟動時在背景載入最新學期的大綱索引（約數秒），避免第一個使用者的查詢卡住"""
    import threading

    def _load():
        df = get_latest_courses_df()
        if df is not None and not df.empty:
            year, semester = resolve_semester(df, None, None)
            get_syllabus_index(int(year), int(semester))
    threading.Thread(target=_load, daemon=True).start()

@app.post("/api/ai/chat")
def ai_chat(request: ChatRequest):
    """選課助理：自然語言需求 → LLM 呼叫工具查課 → 回傳經過驗證、確實存在的課程"""
    from ai.agent import run_agent
    from ai.llm import get_client
    from ai.tools import CourseContext, course_key

    full_df = get_latest_courses_df()
    if full_df is None or full_df.empty:
        raise HTTPException(status_code=404, detail="沒有處理過的課程數據")
    if not request.messages or request.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="最後一則訊息必須是使用者的問題")

    year, semester = resolve_semester(full_df, request.year, request.semester)
    sem_df = select_semester(full_df, year, semester)
    by_key = {course_key(r): r for r in sem_df.to_dict('records')}
    # 前端傳來的現有課表：以資料庫中的版本為準；別學期的課（例如 localStorage 舊資料）照原樣使用
    current = [by_key.get(course_key(c), c) for c in request.current_courses]

    raw_df = get_raw_courses_df()
    ctx = CourseContext(
        semester_df=sem_df, history_df=full_df, year=int(year), semester=int(semester),
        current_courses=current,
        predict=lambda c: prediction_store.get(c, raw_df),
        syllabus_index=get_syllabus_index(int(year), int(semester)),
    )
    try:
        result = run_agent([m.model_dump() for m in request.messages], ctx, get_client(request.provider))
    except Exception as e:
        logging.error(f"選課助理錯誤: {e}")
        raise HTTPException(status_code=500, detail=f"選課助理發生錯誤: {e}")

    courses = clean_course_data(result["courses"])
    attach_historical_rates(courses, calculate_historical_stats(full_df))
    attach_predictions(courses)
    result["courses"] = courses
    result["semester"] = f"{year}-{semester}"
    return result

@app.get("/api/ai/syllabus-search")
def syllabus_search(q: str, k: int = 8, year: Optional[int] = None, semester: Optional[int] = None):
    """用自然語言搜尋教學大綱內容，回傳相關課程與命中的段落"""
    full_df = get_latest_courses_df()
    if full_df is None or full_df.empty:
        raise HTTPException(status_code=404, detail="沒有處理過的課程數據")
    year, semester = resolve_semester(full_df, year, semester)
    index = get_syllabus_index(int(year), int(semester))
    if index is None:
        return {"available": False, "hits": [], "detail": "尚未建立這學期的大綱索引（python main.py fetch-syllabi && python main.py build-index）"}
    sem_df = select_semester(full_df, year, semester)
    from ai.tools import course_key
    by_key = {course_key(r): r for r in sem_df.to_dict('records')}
    hits = []
    for h in index.search(q, k=max(1, min(k, 30))):
        c = by_key.get(course_key({"code": h["code"], "serial": h["serial"]}))
        if c is None:
            continue
        hits.append({**c, "match_section": h["section"], "match_text": h["text"], "match_score": round(float(h["score"]), 4)})
    hits = clean_course_data(hits)
    attach_predictions(hits)
    return {"available": True, "hits": hits, "index": index.info}

class SyllabusQARequest(BaseModel):
    code: str
    serial: str
    question: str
    year: Optional[int] = None
    semester: Optional[int] = None

@app.post("/api/ai/syllabus-qa")
def syllabus_qa(request: SyllabusQARequest):
    """針對單一課程的大綱問答，回答附上引用的原文段落"""
    from ai.index import answer_from_syllabus
    from ai.llm import get_client

    full_df = get_latest_courses_df()
    if full_df is None or full_df.empty:
        raise HTTPException(status_code=404, detail="沒有處理過的課程數據")
    year, semester = resolve_semester(full_df, request.year, request.semester)
    index = get_syllabus_index(int(year), int(semester))
    if index is None:
        raise HTTPException(status_code=404, detail="尚未建立這學期的大綱索引")
    return answer_from_syllabus(index, request.code, request.serial, request.question, get_client())

@app.get("/api/courses/{course_id}")
async def get_course_detail(course_id: str):
    try:
        df = get_latest_courses_df()
        if df is None or df.empty: raise HTTPException(404)
        course = df[df['課程代碼'].astype(str) == str(course_id)]
        if course.empty: raise HTTPException(404)
        return clean_single_course(course.iloc[0].to_dict())
    except HTTPException: raise
    except Exception: raise HTTPException(500)

@app.get("/api/departments")
async def get_departments(year: Optional[int] = None, semester: Optional[int] = None):
    try:
        if year and semester: df = get_courses_by_semester(year, semester)
        else: df = get_latest_courses_df()
        if df is None or df.empty or '開課班別(代表)' not in df.columns: return {"departments": []}
        departments = df['開課班別(代表)'].dropna().unique().tolist()
        departments = [d for d in departments if d and str(d).strip()]
        departments.sort()
        return {"departments": departments}
    except: raise HTTPException(500)

def main():
    setup_logging()
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)

if __name__ == "__main__":
    main()