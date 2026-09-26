import json

import pytest

from ai.agent import run_agent
from ai.llm import MockClient
from ai.parse import course_satisfies, parse_request
from ai.tools import CourseContext, check_schedule_conflict, find_courses
from services.recommend import select_semester


@pytest.fixture
def ctx(sample_df):
    dedup = sample_df.drop_duplicates(["學年度", "學期", "課程代碼", "序號"], keep="last")
    return CourseContext(semester_df=select_semester(dedup, 114, 2), history_df=dedup, year=114, semester=2)


class LyingClient:
    """先正常查課，最後卻推薦一門不存在的課＋一門真的課"""
    name = "lying"

    def __init__(self, real):
        self.real = real

    def chat(self, messages, tools=None, format=None):
        if format is None:
            called = any(m.get("role") == "tool" for m in messages)
            return {"content": "", "tool_calls": [] if called else [{"name": "find_courses", "arguments": {"limit": 3}}]}
        return {"content": json.dumps({"reply": "ok", "suggestions": [
            {"code": "FAKE1", "serial": "999", "reason": "編的"},
            {"code": self.real[0], "serial": self.real[1], "reason": "真的"},
        ]}, ensure_ascii=False), "tool_calls": []}


def test_hallucinated_course_is_dropped(ctx):
    real = next(iter(ctx._by_key))
    res = run_agent([{"role": "user", "content": "隨便推薦"}], ctx, LyingClient(real))
    assert [d["code"] for d in res["dropped"]] == ["FAKE1"]
    assert len(res["courses"]) == 1 and res["courses"][0]["課程代碼"] == real[0]
    assert res["tool_trace"][0]["tool"] == "find_courses"


def test_mock_agent_respects_avoid_days_and_category(ctx):
    q = "星期一和三不想上課，找通識"
    res = run_agent([{"role": "user", "content": q}], ctx, MockClient())
    assert res["courses"], "樣本資料中應有符合的通識課"
    for c in res["courses"]:
        assert all(course_satisfies(c, parse_request(q)).values())


def test_find_courses_excludes_current_and_conflicts(ctx):
    first = ctx.semester_df.dropna(subset=["星期", "起始節次"]).iloc[0].to_dict()
    ctx.current_courses = [first]
    res = find_courses(ctx, limit=30)
    keys = {(c["code"], c["serial"]) for c in res["courses"]}
    assert (str(first["課程代碼"]), str(int(first["序號"]))) not in keys
    for c in res["courses"]:
        assert "時間未定" in c["time"] or c["time"] != ""
    conflict = check_schedule_conflict(ctx, [{"code": str(first["課程代碼"]), "serial": str(int(first["序號"]))}])
    assert conflict["conflicts"], "同一門課和自己一定衝堂"


def test_avoid_days_filters_every_slot(ctx):
    res = find_courses(ctx, avoid_days=["一", "二", "三", "四"], limit=30)
    for c in res["courses"]:
        assert not any(c["time"].startswith(f"週{d}") for d in "一二三四")


def test_unknown_tool_returns_error(ctx):
    from ai.tools import run_tool
    assert "error" in run_tool(ctx, "rm_rf", {})
    assert "error" in run_tool(ctx, "find_courses", {"limit": "not-a-number"})


@pytest.mark.parametrize("text,key,value", [
    ("週五不要有課", "avoid_days", ["五"]),
    ("只要週二或週四", "preferred_days", ["二", "四"]),
    ("2 學分通識", "credits", 2),
    ("不要太難搶", "max_p_full", 0.3),
    ("不要早八", "avoid_first_period", True),
    ("給我三門", "limit", 3),
    ("跟資料分析有關", "keyword", "資料分析"),
])
def test_parse_request(text, key, value):
    assert parse_request(text)[key] == value


def test_chat_endpoint_with_mock(client):
    r = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "找通識"}],
                                          "year": 114, "semester": 2, "provider": "mock"})
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "mock" and body["semester"] == "114-2"
    assert all("ai_reason" in c for c in body["courses"])
    assert client.post("/api/ai/chat", json={"messages": []}).status_code == 400
