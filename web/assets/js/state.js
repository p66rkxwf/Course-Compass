/**
 * 狀態管理
 */
import { DEFAULT_YEAR, DEFAULT_SEMESTER } from './config.js';

export const state = {
    selectedCourses: [],    // 已選課程列表
    currentSchedule: {},    // 當前課表 {day: {period: course}}

    allCoursesData: [],     // 所有課程數據
    currentYear: DEFAULT_YEAR,
    currentSemester: DEFAULT_SEMESTER,
    recommendedCourses: []  // 暫存推薦結果
};

// 初始化課表結構
for (let day = 1; day <= 7; day++) {
    state.currentSchedule[day] = {};
}

export function saveToLocalStorage() {
    try {
        localStorage.setItem('selectedCourses', JSON.stringify(state.selectedCourses));
        localStorage.setItem('currentSchedule', JSON.stringify(state.currentSchedule));

    } catch (error) {
        console.error('保存失敗:', error);
    }
}

export function loadFromLocalStorage() {
    try {
        const savedCourses = localStorage.getItem('selectedCourses');
        const savedSchedule = localStorage.getItem('currentSchedule');
        
        if (savedCourses) state.selectedCourses = JSON.parse(savedCourses);
        if (savedSchedule) state.currentSchedule = JSON.parse(savedSchedule);
    } catch (error) {
        console.error('載入失敗:', error);
    }
}