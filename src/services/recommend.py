"""課程篩選與推薦的純函式。

HTTP 端點（api/app.py）與選課助理的工具（ai/tools.py）共用這裡的邏輯，
避免兩邊各寫一份而行為分歧。
"""

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

GENERAL_CATEGORIES = ["核心通識", "精進中文", "精進英外文", "教育學程", "大二體育", "大三、四體育"]

DAY_NUM_TO_ZH = {'1': '一', '2': '二', '3': '三', '4': '四', '5': '五', '6': '六', '7': '日'}
DAY_ZH_TO_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7}


def clean_course_data(courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """清理課程數據，處理 NaN 並規範型別"""
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


def attach_historical_rates(courses: List[Dict[str, Any]], stats_map: Dict[tuple, float]) -> None:
    for c in courses:
        name = str(c.get('課程名稱') or '').strip()
        teacher = str(c.get('教師姓名') or '').strip()
        c['historical_acceptance_rate'] = stats_map.get((name, teacher), None)


def resolve_semester(full_df: pd.DataFrame, year: Optional[int], semester: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
    """未指定學期時，取資料中最新的學年度與該年最大的學期"""
    if year is not None and semester is not None:
        return year, semester
    current_year = int(full_df['學年度'].max()) if '學年度' in full_df.columns else None
    if current_year:
        try:
            current_semester = int(full_df[full_df['學年度'] == current_year]['學期'].max())
        except Exception:
            current_semester = 1
    else:
        current_semester = 1
    return current_year, current_semester


def select_semester(full_df: pd.DataFrame, year: Optional[int], semester: Optional[int]) -> pd.DataFrame:
    if not year or not semester:
        return pd.DataFrame()
    return full_df[
        (full_df['學年度'].astype(str) == str(year)) &
        (full_df['學期'].astype(str) == str(semester))
    ].copy()


def day_to_num(day: Any) -> Optional[int]:
    if day is None or (isinstance(day, float) and math.isnan(day)):
        return None
    s = str(day).strip()
    if s.isdigit():
        return int(s)
    return DAY_ZH_TO_NUM.get(s)


def _normalize_days(days: Iterable[Any]) -> set:
    """把 ['1', '五', 3] 這類混合寫法都轉成數字 1～7"""
    out = set()
    for d in days or []:
        n = day_to_num(d)
        if n:
            out.add(n)
    return out


def filter_courses(
    target_df: pd.DataFrame,
    category: Optional[str] = None,
    college: Optional[str] = None,
    department: Optional[str] = None,
    grade: Optional[str] = None,
    level: Optional[str] = None,
    preferred_days: Optional[List[str]] = None,
    current_courses: Optional[List[Dict[str, Any]]] = None,
    empty_slots: Optional[List[Dict[str, int]]] = None,
    avoid_days: Optional[List[Any]] = None,
    keyword: Optional[str] = None,
) -> pd.DataFrame:
    """依條件篩選單一學期的課程。前九個參數與原 /api/courses/recommend 的行為一致；
    avoid_days、keyword 為選課助理新增。"""
    filtered = target_df.copy()
    if category:
        if category in GENERAL_CATEGORIES:
            filtered = filtered[filtered['開課班別(代表)'].astype(str).str.contains(category, na=False)]

    if college:
        c = str(college)
        if '學院' in filtered.columns:
            filtered = filtered[filtered['學院'] == c]

    if department:
        d = str(department)
        if '科系' in filtered.columns:
            filtered = filtered[(filtered['科系'] == d) | (filtered['開課班別(代表)'].str.contains(d, na=False))]
        else:
            filtered = filtered[filtered['開課班別(代表)'].str.contains(d, na=False)]

    if grade and '年級' in filtered.columns:
        filtered = filtered[filtered['年級'].astype(str) == str(grade)]

    if level:
        level_col = '部別(大學/碩士/博士)' if '部別(大學/碩士/博士)' in filtered.columns else None
        if not level_col and '部別' in filtered.columns:
            level_col = '部別'

        if level_col:
            filtered = filtered[filtered[level_col].astype(str) == level]
        else:
            mask_phd = filtered['開課班別(代表)'].astype(str).str.contains('博', na=False) | filtered['年級'].astype(str).str.contains('博', na=False)
            mask_master = filtered['開課班別(代表)'].astype(str).str.contains('碩', na=False) | filtered['年級'].astype(str).str.contains('碩', na=False)

            if level == '博士班':
                filtered = filtered[mask_phd]
            elif level == '碩士班':
                filtered = filtered[mask_master & ~mask_phd]
            elif level == '大學部':
                filtered = filtered[~mask_master & ~mask_phd]

    if preferred_days:
        days_set = set(preferred_days)

        def check_day(row_day):
            d_str = str(row_day)
            if d_str in days_set: return True
            if d_str in DAY_NUM_TO_ZH and str(DAY_NUM_TO_ZH[d_str]) in days_set: return True
            for k, v in DAY_NUM_TO_ZH.items():
                if str(v) == d_str and k in days_set: return True
            return False

        if '星期' in filtered.columns:
            filtered = filtered[filtered['星期'].apply(check_day)]

    if current_courses:
        for c in current_courses:
            code, serial = str(c.get('code', '')), str(c.get('serial', ''))
            filtered = filtered[~((filtered['課程代碼'].astype(str) == code) & (filtered['序號'].astype(str) == serial))]

    if empty_slots:
        empty_set = set((int(s['day']), int(s['period'])) for s in empty_slots if s and 'day' in s and 'period' in s)

        def fits(row):
            try:
                d_num = day_to_num(row.get('星期'))
                if not d_num: return False
                s, e = int(row.get('起始節次') or 0), int(row.get('結束節次') or 0)
                if s <= 0 or e <= 0: return False
                for p in range(s, e + 1):
                    if (d_num, p) not in empty_set: return False
                return True
            except Exception:
                return False
        filtered = filtered[filtered.apply(fits, axis=1)]

    if avoid_days:
        # 一門課只要有任何一個時段落在避開的日子就整門排除（資料是一個時段一列）
        avoid = _normalize_days(avoid_days)
        if avoid and '星期' in filtered.columns:
            bad_keys = set(
                zip(*[filtered.loc[filtered['星期'].apply(day_to_num).isin(avoid), k].astype(str) for k in ('課程代碼', '序號')])
            )
            keys = list(zip(filtered['課程代碼'].astype(str), filtered['序號'].astype(str)))
            filtered = filtered[[k not in bad_keys for k in keys]]

    if keyword:
        kw = str(keyword).lower()
        mask = pd.Series(False, index=filtered.index)
        for col in ('課程名稱', '英文課程名稱', '教師姓名', '備註'):
            if col in filtered.columns:
                mask |= filtered[col].astype(str).str.lower().str.contains(kw, na=False, regex=False)
        filtered = filtered[mask]

    return filtered
