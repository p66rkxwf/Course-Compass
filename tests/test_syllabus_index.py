import numpy as np
import pandas as pd

from ai.index import SyllabusIndex, answer_from_syllabus
from ai.llm import MockClient
from ai.syllabus import chunk_text, clean_text, split_sections

RAW = """國立彰化師範大學 115學年度 第1學期
課程大綱暨教學計畫表
授課教師：王小明
科目名稱：資料分析入門
教學意見反應問卷類型：
1.講述 2.討論 3.實習
教學型態：(0)
教學目標：
學會用 Python 做資料分析與視覺化。
評量方式項目 百分比
期中考 30%
期末報告 40%
課
程
對
核
心
能
力
教學內容與進度：
1 課程介紹
"""


def test_clean_text_removes_boilerplate_and_joins_vertical_text():
    t = clean_text(RAW.replace("\n", "\r\n"))
    assert "課程大綱暨教學計畫表" not in t
    assert "問卷類型" not in t and "1.講述" not in t
    assert "課程對核心能力" in t


def test_sections_and_chunks():
    t = clean_text(RAW)
    names = [n for n, _ in split_sections(t)]
    assert names[:3] == ["基本資料", "教學目標", "評量方式"]
    assert names[-1] == "教學進度"
    long = "教學目標：" + "資料分析" * 400
    chunks = chunk_text(long, size=500, overlap=80)
    assert all(len(c) <= 500 for _, c in chunks) and len(chunks) >= 3
    assert chunks[0][1][-80:] == chunks[1][1][:80]  # 相鄰塊重疊


def _tiny_index():
    meta = pd.DataFrame([
        {"code": "A1", "serial": 1, "name": "資料分析入門", "section": "教學目標", "text": "學會用 Python 做資料分析與視覺化"},
        {"code": "A1", "serial": 1, "name": "資料分析入門", "section": "評量方式", "text": "期中考 30% 期末報告 40%"},
        {"code": "B2", "serial": 2, "name": "西洋美術史", "section": "教學目標", "text": "欣賞文藝復興繪畫與雕塑"},
    ])
    client = MockClient()
    vecs = np.asarray(client.embed([f"{n}｜{s}：{t}" for n, s, t in zip(meta.name, meta.section, meta.text)]), dtype=np.float32)
    info = {"year": 115, "semester": 1, "provider": "mock", "embed_model": "mock", "dim": vecs.shape[1]}
    return SyllabusIndex(vecs, meta, info, client)


def test_search_ranks_relevant_course_first_and_respects_semester():
    idx = _tiny_index()
    hits = idx.search("Python 資料分析", k=2)
    assert hits[0]["code"] == "A1"
    assert len({(h["code"], h["serial"]) for h in hits}) == len(hits)  # 每門課只出現一次
    assert idx.search("Python", year=114, semester=2) == []


def test_qa_cites_the_course_own_chunks():
    idx = _tiny_index()
    ans = answer_from_syllabus(idx, "A1", 1, "期中考占多少", MockClient())
    assert ans["citations"] and ans["citations"][0]["section"] == "評量方式"
    none = answer_from_syllabus(idx, "ZZZ", 9, "?", MockClient())
    assert none["citations"] == []
