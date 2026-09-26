"""推薦 API 的特徵測試案例：重構前用舊實作產生 golden，重構後逐案比對。"""

# 空堂：週一～週五第 1～9 節全空，但週三第 5～7 節已有課
EMPTY_SLOTS = [{"day": d, "period": p} for d in range(1, 6) for p in range(1, 10) if not (d == 3 and 5 <= p <= 7)]

CASES = [
    {"target_credits": 20},
    {"year": 114, "semester": 2},
    {"year": 114, "semester": 2, "category": "核心通識"},
    {"year": 114, "semester": 1, "category": "精進英外文"},
    {"year": 114, "semester": 2, "category": "大二體育", "preferred_days": ["2", "4"]},
    {"year": 114, "semester": 2, "college": "管理學院"},
    {"year": 114, "semester": 2, "department": "資訊工程學系"},
    {"year": 114, "semester": 2, "department": "資訊管理學系", "grade": "2"},
    {"year": 114, "semester": 2, "level": "碩士班"},
    {"year": 114, "semester": 2, "level": "大學部", "preferred_days": ["一", "五"]},
    {"year": 114, "semester": 2, "category": "核心通識", "empty_slots": EMPTY_SLOTS},
    {"year": 113, "semester": 1, "category": "核心通識", "current_courses": [{"code": "00227", "serial": "1"}]},
]
