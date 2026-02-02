import os

# --- 課程監控設定 ---
TARGET_YEAR = "114"
TARGET_SEMESTER = "2"
TARGET_COURSES = ["54019", "00342"] # 填入目標代碼

# --- 從環境變數讀取秘密資料 ---
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

BASE_URL = "https://webapss.ncue.edu.tw/DEANV2/Other/OB010"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}