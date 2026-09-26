"""課程爬蟲模組 - 爬取校內課程列表並將原始資料寫入 RAW_DATA_DIR"""

import re
import ssl
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import logging

from config import (
    BASE_URL, BASE_DOMAIN, RAW_DATA_DIR,
    START_YEAR, START_SEMESTER, END_YEAR, END_SEMESTER, CLS_BRANCHES, HTML_PARSER, REQUEST_DELAY_SEC
)
from utils.common import safe_write_csv, get_timestamp

HEADERS = {"User-Agent": "Mozilla/5.0 (Course-Compass crawler)"}

# 新版查詢頁的欄名與舊資料不同，統一回舊欄名，下游處理不必改
HEADER_ALIASES = {"全英語": "全英語授課"}


class _SchoolSSLAdapter(HTTPAdapter):
    """學校憑證缺 Subject Key Identifier，Python 3.13 預設的 X.509 strict 檢查會拒絕。
    只關掉 strict 旗標，憑證鏈與主機名稱照常驗證。"""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class CourseCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.mount("https://", _SchoolSSLAdapter())
        self.logger = logging.getLogger(__name__)

    def get_token(self) -> str:
        """取得 ASP.NET MVC 查詢所需的 __RequestVerificationToken"""
        resp = self.session.get(BASE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, HTML_PARSER)
        token = soup.find("input", {"name": "__RequestVerificationToken"})
        if token is None:
            raise RuntimeError("找不到 __RequestVerificationToken，查詢頁結構可能又改版")
        return token["value"]

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

    def fetch_course_table(self, year: int, semester: int, cls_branch: str = "D") -> Optional[BeautifulSoup]:
        """獲取課程表格（cls_branch: D=日間部、N=夜間部）"""
        token = self.get_token()

        payload = {
            "__RequestVerificationToken": token,
            "sel_cls_branch": cls_branch,
            "sel_scr_english": "",
            "sel_SCR_IS_DIS_LEARN": "",
            "sel_yms_year": str(year),
            "sel_yms_smester": str(semester),
            "scr_selcode": "",
            "sel_cls_id": "",
            "sel_sct_week": "",
            "sub_name": "",
            "emp_name": "",
            "CatchBot": "",  # 防機器人欄位，必須留空
        }
        headers = {**HEADERS, "X-Requested-With": "XMLHttpRequest", "Referer": BASE_URL}

        resp = self.session.post(BASE_URL, data=payload, headers=headers, timeout=120)
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
        headers = [HEADER_ALIASES.get(h, h) for h in headers]
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
                header = headers[idx]

                if header == "課程名稱":
                    # 新版：<strong>中文</strong><br><small>English</small>；舊版：文字節點 + <b>English</b>
                    zh_tag = td.find("strong")
                    if zh_tag is not None:
                        zh_name = zh_tag.get_text(strip=True)
                    else:
                        zh_node = td.find(string=True, recursive=False)
                        zh_name = zh_node.strip() if zh_node else ""
                    en_node = td.find("small") or td.find("b")
                    en_name = en_node.get_text(strip=True) if en_node else ""

                    record["課程名稱"] = zh_name
                    record["英文課程名稱"] = en_name
                elif header == "教師姓名":
                    record["教師姓名"] = td.get_text(strip=True)

                    a = td.find("a")
                    raw = (a.get("onclick") or a.get("href") or "") if a else ""
                    m = re.search(r"OpenWin\('([^']+)'", raw)
                    if m:
                        record["教師個人頁"] = m.group(1)
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
        """爬取單一學期的課程數據（日間部＋夜間部合併）"""
        try:
            self.logger.info(f"開始爬取 {year}-{semester}")
            frames = []
            for branch in CLS_BRANCHES:
                table = self.fetch_course_table(year, semester, branch)
                headers, data = self.parse_course_table(table)
                self.logger.info(f"{year}-{semester} 部別 {branch}: {len(data)} 筆")
                if data:
                    frames.append(pd.DataFrame(data, columns=headers))
                time.sleep(REQUEST_DELAY_SEC)

            if not frames:
                self.logger.warning(f"{year}-{semester} 查無資料")
                return False

            df = pd.concat(frames, ignore_index=True)
            # 各部別的序號都從 1 起算，合併後重編，維持「課程代碼+序號」在學期內唯一
            df["序號"] = range(1, len(df) + 1)

            filename = f"courses_{year}_{semester}.csv"
            filepath = RAW_DATA_DIR / filename
            safe_write_csv(df, filepath)
            self.logger.info(f"成功儲存 {year}-{semester}: {len(df)} 筆資料")
            return True

        except Exception as e:
            self.logger.error(f"爬取 {year}-{semester} 失敗: {e}")
            return False

    def crawl_all_semesters(self, semesters: Optional[List[Tuple[int, int]]] = None) -> None:
        """爬取學期的課程數據；未指定則爬設定檔中的完整區間"""
        semesters = semesters or self.generate_semester_range()
        self.logger.info(f"準備爬取學期: {semesters}")

        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

        for year, semester in semesters:
            self.crawl_semester(year, semester)

def parse_semester_args(values: Optional[List[str]]) -> Optional[List[Tuple[int, int]]]:
    """把 ["114-2", "115-1"] 轉成 [(114, 2), (115, 1)]"""
    if not values:
        return None
    result = []
    for v in values:
        y, s = v.split("-")
        result.append((int(y), int(s)))
    return result

def main(semesters: Optional[List[str]] = None):
    from utils.common import setup_logging
    setup_logging()

    crawler = CourseCrawler()
    crawler.crawl_all_semesters(parse_semester_args(semesters))

if __name__ == "__main__":
    main()