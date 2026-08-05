import os

# --- 課程監控設定 ---
TARGET_YEAR = os.getenv("TARGET_YEAR", "115")
TARGET_SEMESTER = os.getenv("TARGET_SEMESTER", "1")

# 監控的課程代碼。可用環境變數 TARGET_COURSES 以逗號分隔覆寫，換課不必改程式。
TARGET_COURSES = [
    c.strip()
    for c in os.getenv("TARGET_COURSES", "54019,00342").split(",")
    if c.strip()
]

# --- 從環境變數讀取秘密資料 ---
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

BASE_URL = "https://webap0.ncue.edu.tw/DEANV2/Other/OB010"

# 記錄上一輪各課程的缺額狀態，避免有缺額時每次排程都重複推播
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

REQUEST_TIMEOUT = 30
