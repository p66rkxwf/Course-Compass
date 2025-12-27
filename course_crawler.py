import requests
import csv
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path

BASE_URL = "https://webap0.ncue.edu.tw/DEANV2/Other/OB010"
BASE_DOMAIN = "https://webap0.ncue.edu.tw"
OUTPUT_DIR = "raw_data"
START_YEAR = 111
START_SEMESTER = 1
END_YEAR = 114
END_SEMESTER = 1
CLS_BRANCH = ""
HTML_PARSER = "lxml"

def get_viewstate(session):
    """取得 ASP.NET 查詢所需隱藏欄位"""
    resp = session.get(BASE_URL)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, HTML_PARSER)
    viewstate = soup.find("input", {"name": "__VIEWSTATE"})
    eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})

    return (
        viewstate["value"] if viewstate else "",
        eventvalidation["value"] if eventvalidation else ""
    )

def next_semester(year, semester):
    """回傳下一個 (year, semester)"""
    if semester == 1:
        return year, 2
    else:
        return year + 1, 1

def generate_semester_range():
    """產生學期區間 [(year, semester), ...]"""
    result = []
    y, s = START_YEAR, START_SEMESTER

    while True:
        result.append((y, s))
        if y == END_YEAR and s == END_SEMESTER:
            break
        y, s = next_semester(y, s)

    return result

def fetch_course_table(session, year, semester, cls_branch):
    viewstate, eventvalidation = get_viewstate(session)

    payload = {
        "__VIEWSTATE": viewstate,
        "__EVENTVALIDATION": eventvalidation,
        "sel_yms_year": str(year),
        "sel_yms_smester": str(semester),
        "sel_cls_branch": cls_branch,
        "btnQuery": "查詢",
    }

    resp = session.post(BASE_URL, data=payload)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, HTML_PARSER)
    table = soup.find("table", {"class": "table"})

    if table is None:
        raise RuntimeError(f"找不到 {year}-{semester} 的課程資料表")

    return table

def parse_course_table(table):
    rows = table.find_all("tr")

    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]

    try:
        syllabus_idx = next(
            i for i, h in enumerate(headers)
            if "教學大綱" in h or "Syllabus" in h
        )
    except StopIteration:
        syllabus_idx = None

    if syllabus_idx is not None:
        headers.insert(syllabus_idx + 1, "教學大綱連結")
    else:
        headers.append("教學大綱連結")

    data = []

    for row in rows[1:]:
        cols = row.find_all("td")
        if not cols:
            continue

        record = {}
        syllabus_url = None

        for idx, td in enumerate(cols):
            header_idx = idx if syllabus_idx is None or idx <= syllabus_idx else idx + 1
            header = headers[header_idx]
            record[header] = td.get_text(strip=True)

            if syllabus_idx is not None and idx == syllabus_idx:
                a = td.find("a", href=True)
                if a:
                    syllabus_url = urljoin(BASE_DOMAIN, a["href"])

        record["教學大綱連結"] = syllabus_url
        data.append(record)

    return headers, data

def save_to_csv(headers, data, year, semester):
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)
    if not output_path.exists():
        print(f"已建立資料夾：{OUTPUT_DIR}")

    filename = f"courses_{year}_{semester}.csv"
    file_path = output_path / filename

    try:
        with open(str(file_path), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)
        print(f"已成功儲存：{file_path} (共 {len(data)} 筆)")
    except Exception as e:
        print(f"儲存失敗 {file_path}: {e}")

def main():
    session = requests.Session()
    semesters = generate_semester_range()
    abs_output_path = Path(OUTPUT_DIR).resolve()
    print(f"準備將檔案儲存至: {abs_output_path}")
    print("即將爬取學期：", semesters)

    for year, semester in semesters:
        print(f"\n爬取 {year}-{semester} 中...")
        try:
            table = fetch_course_table(session, year, semester, CLS_BRANCH)
            headers, data = parse_course_table(table)

            if not data:
                print(f"⚠ 注意：{year}-{semester} 查無資料")
            
            save_to_csv(headers, data, year, semester)
            
        except Exception as e:
            print(f"錯誤：處理 {year}-{semester} 時發生問題 -> {e}")

if __name__ == "__main__":
    main()