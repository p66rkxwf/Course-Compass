/**
 * API 請求模組
 */
import { API_BASE } from './config.js';

export async function fetchAllCourses(year, semester) {
    const response = await fetch(`${API_BASE}/courses/all?year=${year}&semester=${semester}`);
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
}

export async function fetchDepartments(year, semester) {
    const response = await fetch(`${API_BASE}/departments?year=${year}&semester=${semester}`);
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
}

export async function fetchCoursesByClass(department, grade, className, year, semester) {
    const response = await fetch(`${API_BASE}/courses/by-class?department=${encodeURIComponent(department)}&grade=${encodeURIComponent(grade)}&class_name=${encodeURIComponent(className)}&year=${year}&semester=${semester}`);
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
}

export async function fetchRecommendations(payload) {
    const response = await fetch(`${API_BASE}/courses/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
}

export async function fetchHistory(query) {
    const response = await fetch(`${API_BASE}/courses/history?q=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
}
