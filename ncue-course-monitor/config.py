import os

# 1. 監控學期與課程設定
TARGET_YEAR = "114"
TARGET_SEMESTER = "2"
# 填入你要監控的彰師大課程代碼
TARGET_COURSES = ["54019", "00338"] 

# 2. LINE API 設定 (從環境變數讀取，保護隱私)
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

# 3. 彰師大網站設定
BASE_URL = "https://webapss.ncue.edu.tw/DEANV2/Other/OB010"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."
}