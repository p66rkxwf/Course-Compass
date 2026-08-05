"""NCUE 課程缺額監控 - 偵測目標課程出現空位時以 LINE 推播通知。

請求與解析邏輯共用主專案的 src/crawler/ncue_client.py，避免兩份實作各自失準。
"""

import sys
import json
from pathlib import Path

import requests

# 共用主專案的爬蟲底層（純 requests + bs4，不會拉進 pandas）。
# 注意：設定檔命名為 monitor_config 而非 config，因為 src/config.py 會蓋掉同名模組。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from crawler.ncue_client import (  # noqa: E402
    build_session, fetch_course_table, parse_course_table, find_column_index
)

import monitor_config as config  # noqa: E402


def send_line_message(message):
    if not config.LINE_TOKEN or not config.LINE_USER_ID:
        print("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID，略過推播")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_TOKEN}",
    }
    payload = {"to": config.LINE_USER_ID, "messages": [{"type": "text", "text": message}]}

    resp = requests.post(url, headers=headers, json=payload, timeout=config.REQUEST_TIMEOUT)
    if resp.status_code != 200:
        print(f"❌ LINE 推播失敗 ({resp.status_code}): {resp.text}")
        return False

    print("📨 已發送 LINE 通知")
    return True


def load_state():
    try:
        with open(config.STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def to_int(value):
    text = str(value).strip()
    return int(text) if text.isdigit() else 0


def check_ncue_course():
    session = build_session()
    state = load_state()
    changed = False

    for course_code in config.TARGET_COURSES:
        print(f"🌐 查詢 {config.TARGET_YEAR}-{config.TARGET_SEMESTER} 課程 {course_code} ...")

        # 直接用課程代碼查詢，不必每次拉回近兩千筆的全學期表格
        table = fetch_course_table(
            session, config.BASE_URL, config.TARGET_YEAR, config.TARGET_SEMESTER,
            scr_selcode=course_code, html_parser="html.parser",
            timeout=config.REQUEST_TIMEOUT,
        )

        if table is None:
            print(f"ℹ️ {course_code} 查無資料（代碼可能有誤或該學期尚未開放）")
            continue

        headers, rows = parse_course_table(table)
        # 依表頭名稱定位欄位，避免硬編索引在站台改版時默默錯位
        idx_max = find_column_index(headers, "上限人數")
        idx_reg = find_column_index(headers, "登記人數")
        if idx_max is None or idx_reg is None:
            print(f"❌ 表格缺少人數欄位，站台可能又改版了：{headers}")
            continue

        for row in rows:
            if row.get("課程代碼") != course_code:
                continue

            name = row.get("課程名稱", "")
            serial = row.get("序號", "")
            max_n = to_int(row.get("上限人數"))
            reg_n = to_int(row.get("登記人數"))
            has_vacancy = max_n > reg_n

            key = f"{config.TARGET_YEAR}-{config.TARGET_SEMESTER}-{course_code}-{serial}"
            was_vacant = state.get(key, {}).get("has_vacancy", False)

            print(f"📖 [{course_code}] {name} - 登記/上限: {reg_n}/{max_n}"
                  f"{' ✅有缺額' if has_vacancy else ' ❌額滿'}")

            # 只在「額滿 → 有缺額」的轉換時通知，避免每輪排程重複轟炸
            if has_vacancy and not was_vacant:
                send_line_message(
                    f"🎯 發現缺額！\n{name} ({course_code})\n"
                    f"登記/上限：{reg_n}/{max_n}\n"
                    f"學期：{config.TARGET_YEAR}-{config.TARGET_SEMESTER}"
                )

            if state.get(key, {}).get("has_vacancy") != has_vacancy:
                changed = True
            state[key] = {"has_vacancy": has_vacancy, "name": name,
                          "registered": reg_n, "limit": max_n}

    if changed:
        save_state(state)
        print(f"💾 狀態已更新：{config.STATE_FILE}")


if __name__ == "__main__":
    if not config.TARGET_COURSES:
        print("❌ 未設定任何監控課程（TARGET_COURSES）")
        sys.exit(1)
    check_ncue_course()
