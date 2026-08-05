/**
 * API 請求模組
 */
import { API_BASE } from './config.js';

// 統一錯誤處理：把後端的 detail 帶出來，前端才有辦法顯示「為什麼失敗」而不是一律「請稍後再試」
async function getJson(url) {
    const response = await fetch(url);
    if (!response.ok) {
        let detail = '';
        try {
            const body = await response.json();
            detail = body.detail || '';
        } catch (e) { /* 回應不是 JSON 就沿用預設訊息 */ }
        throw new Error(detail || `請求失敗（${response.status}）`);
    }
    return await response.json();
}

// 把篩選條件組成 query string，陣列以逗號串接（後端 csv_param 會拆開），空值一律略過
function buildQuery(params = {}) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value === null || value === undefined || value === '') return;
        if (Array.isArray(value)) {
            if (value.length === 0) return;
            qs.set(key, value.join(','));
        } else if (typeof value === 'boolean') {
            if (value) qs.set(key, 'true');
        } else {
            qs.set(key, value);
        }
    });
    return qs.toString();
}

export async function fetchAllCourses(year, semester) {
    return await getJson(`${API_BASE}/courses/all?year=${year}&semester=${semester}`);
}

export async function fetchSemesters() {
    return await getJson(`${API_BASE}/semesters`);
}

export async function fetchDepartments(year, semester) {
    return await getJson(`${API_BASE}/departments?year=${year}&semester=${semester}`);
}

/**
 * 課程查詢：關鍵字、篩選、課表感知（空堂／衝堂／剩餘學分）與排序都走這一支。
 * 搜尋與推薦合併後後端也只剩一個實作，前端不再需要兩個函式。
 */
export async function queryCourses(payload) {
    const response = await fetch(`${API_BASE}/courses/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        let detail = '';
        try {
            const body = await response.json();
            detail = body.detail || '';
        } catch (e) { /* 忽略非 JSON 回應 */ }
        throw new Error(detail || `查詢失敗（${response.status}）`);
    }
    return await response.json();
}

export async function fetchHistory(query) {
    return await getJson(`${API_BASE}/courses/history?q=${encodeURIComponent(query)}`);
}

// --- 以下為新增功能 ---

// 篩選選單的可選值（學制、學院、通識分類…），全部由後端依資料推導
export async function fetchFilterOptions(year, semester) {
    return await getJson(`${API_BASE}/filters?${buildQuery({ year, semester })}`);
}

// 統計儀表板
export async function fetchDashboard(year, semester) {
    return await getJson(`${API_BASE}/dashboard?${buildQuery({ year, semester })}`);
}

// 即時缺額（會實際連線學校站台，回應比其他 API 慢）
export async function fetchVacancy(codes, year, semester) {
    return await getJson(`${API_BASE}/vacancy?${buildQuery({ codes, year, semester })}`);
}
