"""課程爬蟲模組 - 爬取校內課程列表並將原始資料寫入 RAW_DATA_DIR"""

import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import logging

from config import (
    BASE_URL, BASE_DOMAIN, RAW_DATA_DIR,
    START_YEAR, START_SEMESTER, END_YEAR, END_SEMESTER, CLS_BRANCH, HTML_PARSER
)
from utils.common import safe_write_csv, get_timestamp

class CourseCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

    def get_viewstate(self) -> Tuple[str, str]:
        """取得 ASP.NET 查詢所需隱藏欄位"""
        resp = self.session.get(BASE_URL)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, HTML_PARSER)
        viewstate = soup.find("input", {"name": "__VIEWSTATE"})
        eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})

        return (
            viewstate["value"] if viewstate else "",
            eventvalidation["value"] if eventvalidation else ""
        )

    @staticmethod
    def next_semester(year: int, semester: int) -> Tuple[int, int]:
        """回傳下一個學期"""
        if semester == 1:
            return year, 2
        else:
            return year + 1, 1

    @staticmethod
    def generate_semester_range() -> List[Tuple[int, int]]:
        """產生學期區間"""
        result = []
        y, s = START_YEAR, START_SEMESTER

        while True:
            result.append((y, s))
            if y == END_YEAR and s == END_SEMESTER:
                break
            y, s = CourseCrawler.next_semester(y, s)

        return result

    def fetch_course_table(self, year: int, semester: int, cls_branch: str = "") -> Optional[BeautifulSoup]:
        """獲取課程表格"""
        viewstate, eventvalidation = self.get_viewstate()

        payload = {
            "__VIEWSTATE": viewstate,
            "__EVENTVALIDATION": eventvalidation,
            "sel_yms_year": str(year),
            "sel_yms_smester": str(semester),
            "sel_cls_branch": cls_branch,
            "btnQuery": "查詢",
        }

        resp = self.session.post(BASE_URL, data=payload)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, HTML_PARSER)
        table = soup.find("table", {"class": "table"})

        if table is None:
            raise RuntimeError(f"找不到 {year}-{semester} 的課程資料表")

        return table

    @staticmethod
    def parse_course_table(table: BeautifulSoup) -> Tuple[List[str], List[Dict[str, Any]]]:
        rows = table.find_all("tr")
        headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
        try:
            syllabus_idx = next(
                i for i, h in enumerate(headers)
                if "教學大綱" in h or "Syllabus" in h
            )
        except StopIteration:
            syllabus_idx = None

        # 補上新欄位
        headers.append("英文課程名稱")
        headers.append("教學大綱狀態")
        headers.append("教學大綱連結")
        headers.append("教師個人頁")

        data = []

        for row in rows[1:]:
            cols = row.find_all("td")
            if not cols:
                continue

            record = {
                "英文課程名稱": "",
                "教學大綱狀態": "",
                "教學大綱連結": "",
                "教師個人頁": ""
            }

            for idx, td in enumerate(cols):
                header = rows[0].find_all("th")[idx].get_text(strip=True)

                if header == "課程名稱":
                    zh_node = td.find(text=True, recursive=False)
                    zh_name = zh_node.strip() if zh_node else ""
                    en_node = td.find("b")
                    en_name = en_node.get_text(strip=True) if en_node else ""

                    record["課程名稱"] = zh_name
                    record["英文課程名稱"] = en_name
                elif header == "教師姓名":
                    record["教師姓名"] = td.get_text(strip=True)

                    a = td.find("a")
                    if a and "OpenWin" in a.get("href", ""):
                        raw = a.get("href")
                        start = raw.find("'") + 1
                        end = raw.rfind("'")
                        if start > 0 and end > start:
                            record["教師個人頁"] = raw[start:end]
                elif syllabus_idx is not None and idx == syllabus_idx:
                    links = td.find_all("a", href=True)
                    has_zh = False
                    has_en = False
                    syllabus_url = ""

                    for a in links:
                        text = a.get_text(strip=True).lower()
                        if "中文" in text:
                            has_zh = True
                            syllabus_url = urljoin(BASE_DOMAIN, a["href"])
                        elif "download" in text:
                            has_en = True

                    if has_zh and has_en:
                        status = "中英"
                    elif has_zh:
                        status = "中文"
                    elif has_en:
                        status = "英文"
                    else:
                        status = "無"

                    record["教學大綱狀態"] = status
                    record["教學大綱連結"] = syllabus_url
                else:
                    record[header] = td.get_text(strip=True)

            data.append(record)

        return headers, data

    def crawl_semester(self, year: int, semester: int) -> bool:
        """爬取單一學期的課程數據"""
        try:
            self.logger.info(f"開始爬取 {year}-{semester}")
            table = self.fetch_course_table(year, semester, CLS_BRANCH)
            headers, data = self.parse_course_table(table)

            if not data:
                self.logger.warning(f"{year}-{semester} 查無資料")
                return False

            filename = f"courses_{year}_{semester}.csv"
            filepath = RAW_DATA_DIR / filename
            safe_write_csv(pd.DataFrame(data, columns=headers), filepath)
            self.logger.info(f"成功儲存 {year}-{semester}: {len(data)} 筆資料")
            return True

        except Exception as e:
            self.logger.error(f"爬取 {year}-{semester} 失敗: {e}")
            return False

    def crawl_all_semesters(self) -> None:
        """爬取所有學期的課程數據"""
        semesters = self.generate_semester_range()
        self.logger.info(f"準備爬取學期: {semesters}")

        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

        for year, semester in semesters:
            self.crawl_semester(year, semester)

def main():
    from utils.common import setup_logging
    setup_logging()

    crawler = CourseCrawler()
    crawler.crawl_all_semesters()

if __name__ == "__main__":
    main()