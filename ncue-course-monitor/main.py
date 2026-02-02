import requests
from bs4 import BeautifulSoup
import config

def send_line_message(message):
    if not config.LINE_TOKEN or not config.LINE_USER_ID: return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.LINE_TOKEN}"}
    payload = {"to": config.LINE_USER_ID, "messages": [{"type": "text", "text": message}]}
    requests.post(url, headers=headers, json=payload)

def check_ncue_course():
    session = requests.Session()
    # 這裡的 Header 必須包含 X-Requested-With 才能騙過 MVC 的 AJAX 檢查
    ajax_headers = config.HEADERS.copy()
    ajax_headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "Referer": config.BASE_URL
    })

    try:
        print(f"🌐 步驟 1: 取得 CSRF 令牌 (__RequestVerificationToken)...")
        init_resp = session.get(config.BASE_URL, headers=config.HEADERS, timeout=15)
        soup = BeautifulSoup(init_resp.text, "html.parser")
        
        # 抓取 MVC 必備的 Token
        token_tag = soup.find("input", {"name": "__RequestVerificationToken"})
        if not token_tag:
            print("❌ 失敗：找不到驗證令牌，請確認網址是否正確。")
            return
        
        token = token_tag["value"]
        print(f"✅ 取得 Token: {token[:10]}...")

        # 步驟 2: 準備 POST Payload (根據你的分析補全欄位)
        payload = {
            "__RequestVerificationToken": token,
            "sel_cls_branch": "",   # 日夜間別
            "sel_yms_year": config.TARGET_YEAR,
            "sel_yms_smester": config.TARGET_SEMESTER,
            "sel_scj_cls_id": "",   # 修課班別
            "scr_selcode": "",      # 課程代碼 (如果要查全部就留空)
            "sub_name": "",         # 課程名稱關鍵字
            "tea_name": "",         # 老師姓名
            "btnQuery": "查詢"
        }

        print(f"📡 步驟 3: 模擬 AJAX 發送查詢請求...")
        # 注意：ASP.NET MVC 接收的是 Form Data
        resp = session.post(config.BASE_URL, data=payload, headers=ajax_headers, timeout=20)
        
        if resp.status_code != 200:
            print(f"❌ 查詢失敗，伺服器回傳狀態碼: {resp.status_code}")
            return

        # 步驟 4: 解析回傳的 HTML 片段
        final_soup = BeautifulSoup(resp.text, "html.parser")
        table = final_soup.find("table", {"class": "table"})
        
        if not table:
            print("ℹ️ 查詢成功，但目前無課程資料或條件過於嚴苛。")
            return

        rows = table.find_all("tr")[1:]
        print(f"✅ 成功解析表格，共有 {len(rows)} 門課程。")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 13: continue
            
            c_id = cols[1].get_text(strip=True)
            if c_id in config.TARGET_COURSES:
                c_name = cols[3].get_text(strip=True)
                max_n = int(cols[11].get_text(strip=True) or 0)
                cur_n = int(cols[12].get_text(strip=True) or 0)
                
                print(f"📖 [{c_id}] {c_name} - 名額: {cur_n}/{max_n}")
                if max_n > cur_n:
                    send_line_message(f"🎯 發現缺額！\n{c_name} ({c_id})\n名額：{cur_n}/{max_n}")

    except Exception as e:
        print(f"💥 錯誤: {e}")

if __name__ == "__main__":
    check_ncue_course()