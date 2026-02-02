import requests
from bs4 import BeautifulSoup
import config

def send_line_message(message):
    if not config.LINE_TOKEN or not config.LINE_USER_ID:
        print("⚠️ 錯誤：找不到 LINE 憑證，請檢查環境變數。")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_TOKEN}"
    }
    payload = {
        "to": config.LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    
    try:
        requests.post(url, headers=headers, json=payload)
        print("✅ LINE 通知發送成功！")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def check_ncue_course():
    session = requests.Session()
    try:
        # 1. 初始化取得隱藏欄位
        init_resp = session.get(config.BASE_URL, headers=config.HEADERS)
        soup = BeautifulSoup(init_resp.text, "html.parser")
        viewstate = soup.find("input", {"name": "__VIEWSTATE"})["value"]
        eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})["value"]

        # 2. 查詢指定學期
        payload = {
            "__VIEWSTATE": viewstate,
            "__EVENTVALIDATION": eventvalidation,
            "sel_yms_year": config.TARGET_YEAR,
            "sel_yms_smester": config.TARGET_SEMESTER,
            "btnQuery": "查詢",
        }
        
        resp = session.post(config.BASE_URL, data=payload, headers=config.HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"class": "table"})
        
        if not table: return

        # 3. 判斷名額
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) < 13: continue
            
            c_id = cols[1].get_text(strip=True)
            if c_id in config.TARGET_COURSES:
                c_name = cols[3].get_text(strip=True)
                max_n = int(cols[11].get_text(strip=True))
                cur_n = int(cols[12].get_text(strip=True))
                
                print(f"🔍 檢查：[{c_id}] {c_name} ({cur_n}/{max_n})")
                
                if max_n > cur_n:
                    send_line_message(f"🟢 發現缺額！\n課名：{c_name}\n代碼：{c_id}\n名額：{cur_n}/{max_n}")

    except Exception as e:
        print(f"💥 發生錯誤: {e}")

if __name__ == "__main__":
    check_ncue_course()