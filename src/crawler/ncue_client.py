"""彰師大課程查詢站 (OB010) 的低階存取層。

只依賴 requests + BeautifulSoup，刻意不 import pandas 或本專案的 config 套件，
讓主爬蟲 (`crawler.py`) 與缺額監控 (`ncue-course-monitor/`) 能共用同一份請求與
解析邏輯，避免兩邊各自維護一份而再度失準。

站台已由 ASP.NET WebForms 改版為 MVC：
  - 驗證欄位從 __VIEWSTATE / __EVENTVALIDATION 換成 __RequestVerificationToken
  - 查詢改走 unobtrusive AJAX，必須帶 X-Requested-With 標頭
  - 表單多了名為 CatchBot 的 honeypot 欄位，必須存在且留空
  - 送出舊版 payload 會得到 HTTP 500
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 站台表頭與本專案既有 raw CSV 欄名的對應。改版後「全英語授課」被改名為
# 「全英語」，而 data_processor 與前端都以舊名為 key，故在此正規化回來。
HEADER_ALIASES = {
    "全英語": "全英語授課",
}

# 解析時額外衍生的欄位，接在站台原生表頭之後（順序需與既有 raw CSV 一致）
DERIVED_COLUMNS = ["英文課程名稱", "教學大綱狀態", "教學大綱連結", "教師個人頁"]


def build_session(user_agent: str = DEFAULT_USER_AGENT) -> requests.Session:
    """建立帶瀏覽器 UA 的 session（token 與 cookie 必須成對，務必重用同一個）"""
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def get_request_token(session: requests.Session, base_url: str, timeout: int = 90) -> str:
    """GET 查詢頁並取出 MVC 防偽 token"""
    resp = session.get(base_url, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    token_tag = soup.find("input", {"name": "__RequestVerificationToken"})
    if not token_tag or not token_tag.get("value"):
        raise RuntimeError(f"在 {base_url} 找不到 __RequestVerificationToken，站台可能又改版了")

    return token_tag["value"]


def build_query_payload(
    token: str,
    year: Any,
    semester: Any,
    cls_branch: str = "",
    cls_id: str = "",
    scr_selcode: str = "",
    sub_name: str = "",
    emp_name: str = "",
) -> Dict[str, str]:
    """組出查詢表單內容（欄位名稱依實際頁面表單，缺一不可）"""
    return {
        "__RequestVerificationToken": token,
        "sel_cls_branch": cls_branch,
        "sel_cls_id": cls_id,
        "sel_yms_year": str(year),
        "sel_yms_smester": str(semester),
        "scr_selcode": scr_selcode,
        "sub_name": sub_name,
        "emp_name": emp_name,
        "sel_scr_english": "",
        "sel_sct_week": "",
        "sel_SCR_IS_DIS_LEARN": "",
        "CatchBot": "",  # honeypot：必須存在且留空
    }


def fetch_course_table(
    session: requests.Session,
    base_url: str,
    year: Any,
    semester: Any,
    *,
    cls_branch: str = "",
    scr_selcode: str = "",
    html_parser: str = "lxml",
    timeout: int = 90,
) -> Optional[BeautifulSoup]:
    """查詢單一學期（或單一課程代碼）並回傳結果表格；查無資料回傳 None"""
    token = get_request_token(session, base_url, timeout=timeout)

    payload = build_query_payload(
        token, year, semester, cls_branch=cls_branch, scr_selcode=scr_selcode
    )
    headers = {
        "X-Requested-With": "XMLHttpRequest",  # MVC 端會檢查是否為 AJAX 請求
        "Referer": base_url,
    }

    resp = session.post(base_url, data=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()

    return BeautifulSoup(resp.text, html_parser).find("table", {"class": "table"})


def _parse_course_name(td) -> Tuple[str, str]:
    """課程名稱儲存格：新版為 <strong>中文</strong><br><small>English</small>，
    舊版為直接文字節點 + <b>English</b>。兩種都支援。"""
    zh_node = td.find("strong")
    en_node = td.find("small") or td.find("b")

    if zh_node is not None:
        zh_name = zh_node.get_text(strip=True)
    else:
        raw = td.find(string=True, recursive=False)
        zh_name = raw.strip() if raw else ""

    en_name = en_node.get_text(strip=True) if en_node is not None else ""
    return zh_name, en_name


def _parse_teacher_page(td) -> str:
    """教師個人頁：新版放在 onclick="OpenWin('URL', '標題')"，舊版放在 href"""
    anchor = td.find("a")
    if not anchor:
        return ""

    raw = anchor.get("onclick") or anchor.get("href") or ""
    if "OpenWin" not in raw:
        return ""

    match = re.search(r"OpenWin\(\s*['\"]([^'\"]+)['\"]", raw)
    return match.group(1) if match else ""


def _parse_syllabus(td, base_domain: str) -> Tuple[str, str]:
    """教學大綱：中文連結文字為「中文下載」，英文為「Download」"""
    has_zh = False
    has_en = False
    zh_url = ""
    en_url = ""

    for anchor in td.find_all("a", href=True):
        text = anchor.get_text(strip=True)
        if "中文" in text:
            has_zh = True
            zh_url = urljoin(base_domain, anchor["href"])
        elif "download" in text.lower():
            has_en = True
            en_url = urljoin(base_domain, anchor["href"])

    if has_zh and has_en:
        status = "中英"
    elif has_zh:
        status = "中文"
    elif has_en:
        status = "英文"
    else:
        status = "無"

    return status, (zh_url or en_url)


def parse_course_table(
    table: BeautifulSoup, base_domain: str = ""
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """把結果表格轉成 (欄位順序, 每列 dict)，欄名已套用 HEADER_ALIASES"""
    rows = table.find_all("tr")
    if not rows:
        return [], []

    raw_headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
    headers = [HEADER_ALIASES.get(h, h) for h in raw_headers]

    syllabus_idx = next(
        (i for i, h in enumerate(headers) if "教學大綱" in h or "Syllabus" in h), None
    )

    data = []
    for row in rows[1:]:
        cols = row.find_all("td")
        if not cols:
            continue

        record: Dict[str, Any] = {col: "" for col in DERIVED_COLUMNS}

        for idx, td in enumerate(cols):
            if idx >= len(headers):
                break
            header = headers[idx]

            if header == "課程名稱":
                record["課程名稱"], record["英文課程名稱"] = _parse_course_name(td)
            elif header == "教師姓名":
                record["教師姓名"] = td.get_text(strip=True)
                record["教師個人頁"] = _parse_teacher_page(td)
            elif idx == syllabus_idx:
                # 大綱本身的文字不留存（與既有 111~114 raw 檔一致），只留狀態與連結
                record["教學大綱狀態"], record["教學大綱連結"] = _parse_syllabus(td, base_domain)
            else:
                record[header] = td.get_text(strip=True)

        data.append(record)

    return headers + DERIVED_COLUMNS, data


def find_column_index(headers: List[str], name: str) -> Optional[int]:
    """依表頭名稱找欄位索引，避免硬編索引在站台改版時默默錯位"""
    normalized = [HEADER_ALIASES.get(h, h) for h in headers]
    return normalized.index(name) if name in normalized else None
