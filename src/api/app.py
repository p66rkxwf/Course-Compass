from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from config import PROCESSED_DATA_DIR, WEB_DIR, API_HOST, API_PORT, LOG_LEVEL, LOG_FORMAT, LOG_FILE, LOG_DIR
from utils.common import safe_read_csv, setup_logging

def clean_course_data(courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """清理課程數據，處理 NaN 並規範型別"""
    import math
    cleaned = []
    for course in courses:
        cleaned_course = {}
        for key, value in course.items():
            if isinstance(value, float) and math.isnan(value):
                cleaned_course[key] = None
            else:
                cleaned_course[key] = value
        for fld in ['起始節次', '結束節次']:
            if fld in cleaned_course and cleaned_course[fld] is not None:
                try:
                    num = float(cleaned_course[fld])
                    if num.is_integer():
                        cleaned_course[fld] = int(num)
                except Exception:
                    pass
        cleaned.append(cleaned_course)
    return cleaned

def clean_single_course(course: Dict[str, Any]) -> Dict[str, Any]:
    import math
    cleaned_course = {}
    for key, value in course.items():
        if isinstance(value, float) and math.isnan(value):
            cleaned_course[key] = None
        else:
            cleaned_course[key] = value
    return cleaned_course

def calculate_historical_stats(full_df: pd.DataFrame) -> Dict[tuple, float]:
    """計算每門課（同名稱+同教師）的歷年平均選上率"""
    if full_df is None or full_df.empty:
        return {}
    
    if '登記人數' not in full_df.columns or '上限人數' not in full_df.columns:
        return {}

    df = full_df.copy()
    df['登記人數'] = pd.to_numeric(df['登記人數'], errors='coerce').fillna(0)
    df['上限人數'] = pd.to_numeric(df['上限人數'], errors='coerce').fillna(0)
    
    df['課程名稱'] = df['課程名稱'].fillna('').astype(str).str.strip()
    df['教師姓名'] = df['教師姓名'].fillna('').astype(str).str.strip()

    valid_mask = (df['登記人數'] > 0) & (df['上限人數'] > 0)
    valid_df = df[valid_mask].copy()

    if valid_df.empty:
        return {}

    valid_df['acceptance_rate'] = valid_df['上限人數'] / valid_df['登記人數']
    valid_df['acceptance_rate'] = valid_df['acceptance_rate'].clip(upper=1.0)
    
    avg_rates = valid_df.groupby(['課程名稱', '教師姓名'])['acceptance_rate'].mean().to_dict()
    
    return avg_rates

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

        for c in courses:
            name = str(c.get('課程名稱') or '').strip()
            teacher = str(c.get('教師姓名') or '').strip()
            c['historical_acceptance_rate'] = stats_map.get((name, teacher), None)

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
        
        if request.year is not None and request.semester is not None:
            current_year, current_semester = request.year, request.semester
        else:
            current_year = int(full_df['學年度'].max()) if '學年度' in full_df.columns else None
            if current_year:
                try:
                    current_semester = int(full_df[full_df['學年度'] == current_year]['學期'].max())
                except: current_semester = 1
            else: current_semester = 1

        target_df = pd.DataFrame()
        if current_year and current_semester:
            target_df = full_df[
                (full_df['學年度'].astype(str) == str(current_year)) & 
                (full_df['學期'].astype(str) == str(current_semester))
            ].copy()
        
        if target_df.empty:
            return CourseResponse(courses=[], total=0)
        
        filtered = target_df.copy()
        if request.category:
             if request.category in ["核心通識", "精進中文", "精進英外文", "教育學程", "大二體育", "大三、四體育"]:
                filtered = filtered[filtered['開課班別(代表)'].astype(str).str.contains(request.category, na=False)]
        
        if request.college:
            c = str(request.college)
            if '學院' in filtered.columns:
                filtered = filtered[filtered['學院'] == c]

        if request.department:
            d = str(request.department)
            if '科系' in filtered.columns:
                 filtered = filtered[(filtered['科系'] == d) | (filtered['開課班別(代表)'].str.contains(d, na=False))]
            else:
                 filtered = filtered[filtered['開課班別(代表)'].str.contains(d, na=False)]

        if request.grade and '年級' in filtered.columns:
             filtered = filtered[filtered['年級'].astype(str) == str(request.grade)]

        if request.level:
            level_col = '部別(大學/碩士/博士)' if '部別(大學/碩士/博士)' in filtered.columns else None
            if not level_col and '部別' in filtered.columns:
                level_col = '部別'

            if level_col:
                filtered = filtered[filtered[level_col].astype(str) == request.level]
            else:
                mask_phd = filtered['開課班別(代表)'].astype(str).str.contains('博', na=False) | filtered['年級'].astype(str).str.contains('博', na=False)
                mask_master = filtered['開課班別(代表)'].astype(str).str.contains('碩', na=False) | filtered['年級'].astype(str).str.contains('碩', na=False)

                if request.level == '博士班':
                    filtered = filtered[mask_phd]
                elif request.level == '碩士班':
                    filtered = filtered[mask_master & ~mask_phd]
                elif request.level == '大學部':
                    filtered = filtered[~mask_master & ~mask_phd]

        if request.preferred_days:
            day_map = {'1':'一', '2':'二', '3':'三', '4':'四', '5':'五', '6':'六', '7':'日'}
            days_set = set(request.preferred_days)
            
            def check_day(row_day):
                d_str = str(row_day)
                if d_str in days_set: return True
                if d_str in day_map and str(day_map[d_str]) in days_set: return True
                for k, v in day_map.items():
                    if str(v) == d_str and k in days_set: return True
                return False

            if '星期' in filtered.columns:
                filtered = filtered[filtered['星期'].apply(check_day)]

        if request.current_courses:
            for c in request.current_courses:
                code, serial = str(c.get('code','')), str(c.get('serial',''))
                filtered = filtered[~((filtered['課程代碼'].astype(str)==code) & (filtered['序號'].astype(str)==serial))]

        if request.empty_slots:
            empty_set = set((int(s['day']), int(s['period'])) for s in request.empty_slots if s and 'day' in s and 'period' in s)
            def fits(row):
                try:
                    day = row.get('星期')
                    if pd.isna(day): return False
                    if str(day).isdigit(): d_num = int(day)
                    else: d_num = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'日':7}.get(str(day))
                    if not d_num: return False
                    s, e = int(row.get('起始節次') or 0), int(row.get('結束節次') or 0)
                    if s <= 0 or e <= 0: return False
                    for p in range(s, e+1):
                        if (d_num, p) not in empty_set: return False
                    return True
                except: return False
            filtered = filtered[filtered.apply(fits, axis=1)]

        history_df = get_all_historical_courses_df()
        stats_map = calculate_historical_stats(history_df)

        results_list = filtered.head(50).to_dict('records')
        results_list = clean_course_data(results_list)
        
        for c in results_list:
            name = str(c.get('課程名稱') or '').strip()
            teacher = str(c.get('教師姓名') or '').strip()
            c['historical_acceptance_rate'] = stats_map.get((name, teacher), None)

        return CourseResponse(courses=results_list, total=len(results_list))
        
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