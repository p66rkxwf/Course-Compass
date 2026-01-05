import * as config from './config.js';
import { state, saveToLocalStorage, loadFromLocalStorage } from './state.js';
import * as api from './api.js';
import * as utils from './utils.js';
import * as ui from './ui.js';

let historyGroupsCache = [];
let historyChartInstance = null;

document.addEventListener('DOMContentLoaded', initializeApp);

async function initializeApp() {
    ui.initializeScheduleTable();
    await loadCoursesData();
    populateCollegeSelect();
    initSystemAndLevelSelects();
    await loadDepartments();
    setupEventListeners();
    loadFromLocalStorage();
    cleanupSelectedCourses();
    window.debugState = state;
    ui.updateScheduleDisplay();
    ui.updateSelectedCoursesList();
    exposeGlobalFunctions();

    if (window.toggleScheduleView) {
        const pref = localStorage.getItem('scheduleViewPref');
        window.toggleScheduleView(pref === 'cards' ? 'cards' : 'table');
    }

    window.addEventListener('resize', debounce(detectAndApplyScheduleView, 200));
    detectAndApplyScheduleView();
}

function cleanupSelectedCourses() {
    if (!state.selectedCourses || state.selectedCourses.length === 0) return;
    const unique = [];
    const seen = new Set();
    let hasDuplicate = false;
    state.selectedCourses.forEach(c => {
        const key = `${c.課程代碼}_${c.序號}`;
        if (!seen.has(key)) {
            seen.add(key);
            unique.push(c);
        } else {
            hasDuplicate = true;
        }
    });
    if (hasDuplicate) {
        console.log(`[System] Cleaned duplicate courses`);
        state.selectedCourses = unique;
        saveToLocalStorage();
    }
}

async function loadCoursesData() {
    try {
        const data = await api.fetchAllCourses(state.currentYear, state.currentSemester);
        state.allCoursesData = (data.courses || []).map(c => utils.normalizeCourse ? utils.normalizeCourse(c) : c);
        console.log(`載入 ${state.allCoursesData.length} 門課程`);
        populateCollegeSelect();
        initSystemAndLevelSelects();
    } catch (error) {
        console.error(error);
        ui.showAlert('載入課程數據失敗', 'danger');
    }
}

function getCourseSystem(course) {
    if (course.學制) return course.學制;
    const className = course['開課班別(代表)'] || course.班級 || '';
    return className.includes('夜') ? '夜間部' : '日間部';
}

function getCourseLevel(course) {
    if (course.部別) return course.部別;
    const className = course['開課班別(代表)'] || course.班級 || '';
    const grade = String(course.年級 || '');
    if (className.includes('博') || grade.includes('博')) return '博士班';
    if (className.includes('碩') || grade.includes('碩')) return '碩士班';
    return '大學部';
}

function populateCollegeSelect() {
    const select = document.getElementById('select-college-schedule');
    if (!select) return;
    const current = select.value;
    const colleges = new Set();
    state.allCoursesData.forEach(c => { if(c.學院) colleges.add(c.學院); });
    select.innerHTML = '<option value="">選擇學院</option>';
    Array.from(colleges).sort().forEach(c => select.add(new Option(c, c)));
    if (current && colleges.has(current)) select.value = current;
}

function initSystemAndLevelSelects() {
    const sysSelect = document.getElementById('select-system-schedule');
    const lvlSelect = document.getElementById('select-level-schedule');
    if (!sysSelect || !lvlSelect) return;
    const curSys = sysSelect.value;
    const curLvl = lvlSelect.value;
    sysSelect.innerHTML = '<option value="">全部學制</option>';
    lvlSelect.innerHTML = '<option value="">全部部別</option>';
    const systems = new Set();
    const levels = new Set();
    state.allCoursesData.forEach(c => {
        systems.add(getCourseSystem(c));
        levels.add(getCourseLevel(c));
    });
    Array.from(systems).sort().reverse().forEach(s => sysSelect.add(new Option(s, s)));
    const levelOrder = ['大學部', '碩士班', '博士班'];
    Array.from(levels).sort((a, b) => {
        const ia = levelOrder.indexOf(a), ib = levelOrder.indexOf(b);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    }).forEach(l => lvlSelect.add(new Option(l, l)));
    if (curSys && systems.has(curSys)) sysSelect.value = curSys;
    if (curLvl && levels.has(curLvl)) lvlSelect.value = curLvl;
}

async function loadDepartments() {
    try {
        const data = await api.fetchDepartments(state.currentYear, state.currentSemester);
        const departments = data.departments || [];
        const select = document.getElementById('select-dept-recommend'); 
        if (select) {
            select.innerHTML = '<option value="">選擇系所</option>';
            departments.forEach(dept => {
                select.add(new Option(dept, dept));
            });
        }
    } catch (error) {
        console.error('載入系所列表失敗:', error);
    }
}

async function loadDepartmentsByCollege(college, targetSelectId) {
    try {
        if (state.allCoursesData.length === 0) await loadCoursesData();
        const departments = new Set();
        state.allCoursesData.forEach(course => {
            if (course.學院 === college && course.科系) {
                departments.add(course.科系);
            }
        });
        const select = document.getElementById(targetSelectId);
        if (select) {
            select.innerHTML = '<option value="">選擇科系</option>';
            Array.from(departments).sort().forEach(dept => {
                select.add(new Option(dept, dept));
            });
        }
    } catch (error) {
        console.error('載入科系列表失敗:', error);
    }
}

function updateGradeList(college, department, system, level) {
    const select = document.getElementById('select-grade-schedule');
    select.innerHTML = '<option value="">選擇年級</option>';
    const grades = new Set();
    state.allCoursesData.forEach(course => {
        const matchCollege = course.學院 === college;
        const matchDept = course.科系 === department;
        const matchSys = system === "" || getCourseSystem(course) === system;
        const matchLvl = level === "" || getCourseLevel(course) === level;
        if (matchCollege && matchDept && matchSys && matchLvl && course.年級) {
            grades.add(String(course.年級));
        }
    });
    Array.from(grades).sort((a, b) => {
        const numA = parseInt(a.match(/\d+/)?.[0] || 0);
        const numB = parseInt(b.match(/\d+/)?.[0] || 0);
        if (numA !== numB) return numA - numB;
        return a.localeCompare(b);
    }).forEach(g => {
        let label = g;
        if (/^\d+$/.test(g)) label = `${g}年級`;
        else if (g.includes('碩')) label = g.replace(/(\d+)/, '士$1年級').replace('碩士', '碩士');
        else if (g.includes('博')) label = g.replace(/(\d+)/, '士$1年級').replace('博士', '博士');
        select.add(new Option(label, g));
    });
}

function updateClassList(college, department, system, level, grade) {
    const select = document.getElementById('select-class-schedule');
    select.innerHTML = '<option value="">選擇班級</option>';
    const classMap = new Map();
    state.allCoursesData.forEach(course => {
        const matchCollege = course.學院 === college;
        const matchDept = course.科系 === department;
        const matchGrade = String(course.年級) === String(grade);
        const matchSys = system === "" || getCourseSystem(course) === system;
        const matchLvl = level === "" || getCourseLevel(course) === level;
        if (matchCollege && matchDept && matchGrade && matchSys && matchLvl) {
            let className = course.班級;
            if (!className && course['開課班別(代表)']) {
                 const m = course['開課班別(代表)'].match(/(\d+年級[AB]?班?)/);
                 if (m) className = m[1];
            }
            if (className) {
                const realSystem = getCourseSystem(course);
                const realLevel = getCourseLevel(course);
                const key = `${realSystem}|${realLevel}|${className}`;
                if (!classMap.has(key)) {
                    classMap.set(key, { name: className, value: key });
                }
            }
        }
    });
    Array.from(classMap.values())
        .sort((a, b) => a.name.localeCompare(b.name))
        .forEach(item => select.add(new Option(item.name, item.value)));
}

async function handleImportCourses() {
    const college = document.getElementById('select-college-schedule').value;
    const department = document.getElementById('select-department-schedule').value;
    const grade = document.getElementById('select-grade-schedule').value;
    const compositeClassValue = document.getElementById('select-class-schedule').value;

    if (!college || !department || !grade || !compositeClassValue) {
        ui.showAlert('請完整選擇所有條件', 'warning');
        return;
    }

    const [targetSystem, targetLevel, targetClassName] = compositeClassValue.split('|');
    const btn = document.getElementById('btn-import');
    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>處理中...';

    try {
        const targetCourses = state.allCoursesData.filter(course => {
            if (course.學院 !== college) return false;
            if (course.科系 !== department) return false;
            if (String(course.年級) !== String(grade)) return false;
            if (getCourseSystem(course) !== targetSystem) return false;
            if (getCourseLevel(course) !== targetLevel) return false;
            const cClass = course.班級 || '';
            if (cClass !== targetClassName) {
                if (!course['開課班別(代表)'] || !course['開課班別(代表)'].includes(targetClassName)) {
                    return false;
                }
            }
            return true;
        });

        if (targetCourses.length === 0) {
            ui.showAlert('查無符合條件的課程', 'warning');
            btn.disabled = false;
            btn.innerHTML = originalText;
            return;
        }

        const uniqueTargets = [];
        const seenTargets = new Set();
        targetCourses.forEach(c => {
            const key = `${c.課程代碼}_${c.序號}`;
            if (!seenTargets.has(key)) {
                seenTargets.add(key);
                uniqueTargets.push(c);
            }
        });

        await new Promise(r => setTimeout(r, 200));
        let addedCount = 0;
        let skippedCount = 0;

        for (const rawCourse of uniqueTargets) {
            const course = utils.normalizeCourse(rawCourse);
            if (utils.isCourseSelected(course)) {
                skippedCount++;
                continue;
            }
            let resolved = false;
            while (!resolved) {
                const check = utils.checkTimeConflict(course);
                if (!check.hasConflict) {
                    utils.addCourseToState(course);
                    addedCount++;
                    resolved = true;
                } else {
                    const existingCourse = check.conflictingCourse;
                    const userChoice = await ui.showConflictResolutionModal(course, existingCourse);
                    if (userChoice === 'replace') {
                        utils.removeCourseFromState(existingCourse.課程代碼, existingCourse.序號);
                    } else {
                        skippedCount++;
                        resolved = true; 
                    }
                }
            }
        }
        ui.updateScheduleDisplay();
        ui.updateSelectedCoursesList();
        saveToLocalStorage();
        if (addedCount > 0) {
            ui.showAlert(`成功導入 ${addedCount} 門課程${skippedCount > 0 ? ` (略過 ${skippedCount} 門)` : ''}`, 'success');
        } else {
            ui.showAlert('未導入任何新課程 (皆已存在或選擇略過)', 'info');
        }
    } catch (error) {
        console.error(error);
        ui.showAlert('導入過程發生錯誤', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

function handleClearSchedule() {
    Swal.fire({
        title: '確定要清空所有課程嗎？',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '確定',
        cancelButtonText: '取消'
    }).then(result => {
        if (result.isConfirmed) {
            state.selectedCourses = [];
            state.currentSchedule = {};
            for (let day = 1; day <= 7; day++) state.currentSchedule[day] = {};
            ui.updateScheduleDisplay();
            ui.updateSelectedCoursesList();
            saveToLocalStorage();
            ui.showAlert('課表已清空', 'info');
        }
    });
}

async function handleSearchRecommend() {
    const emptySlotsOnly = document.getElementById('check-empty-slots').checked;
    const selectedDays = Array.from(document.querySelectorAll('.day-filter:checked')).map(cb => cb.value);

    if (selectedDays.length === 0) {
        ui.showAlert('請至少選擇一天', 'warning');
        return;
    }

    const targetCredits = 99; 
    const activeCategory = document.querySelector('.category-btn.active');
    const category = activeCategory ? activeCategory.dataset.category : '核心通識';
    const userCollege = document.getElementById('select-college-schedule').value;
    
    let searchCollege = document.getElementById('select-college').value;
    let searchDept = document.getElementById('select-dept-recommend') ? document.getElementById('select-dept-recommend').value : null;
    let searchGrade = document.getElementById('select-grade').value;

    const isGlobalCategory = [
        '核心通識', '精進中文', '精進英外文', 
        '教育學程', '大二體育', '大三、四體育'
    ].includes(category);

    if (isGlobalCategory) {
        searchCollege = null;
        searchDept = null;
        searchGrade = null;
    }

    if (emptySlotsOnly && utils.getEmptySlots().length === 0) {
        ui.showAlert('目前沒有空堂，請取消「只顯示空堂」或先清空課表', 'warning');
        return;
    }

    let searchYear = state.currentYear;
    let searchSemester = state.currentSemester;
    if (state.selectedCourses.length > 0) {
        const firstCourse = state.selectedCourses[0];
        if (firstCourse.學年度 && firstCourse.學期) {
            searchYear = parseInt(firstCourse.學年度);
            searchSemester = parseInt(firstCourse.學期);
        }
    }

    const btn = document.getElementById('btn-search-recommend');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>搜尋中...';

    try {        
        let apiCategory = category;
        if (category === '系外選修' && !searchDept) {
            throw new Error('請選擇「系外選修」的目標學院與科系');
        }

        const payload = {
            empty_slots: emptySlotsOnly ? utils.getEmptySlots() : null,
            target_credits: targetCredits, 
            category: apiCategory,
            college: searchCollege || null,
            department: searchDept || null,
            grade: searchGrade || null,
            current_courses: state.selectedCourses.map(c => ({ code: c.課程代碼, serial: c.序號 })),
            year: searchYear,
            semester: searchSemester,
            preferred_days: selectedDays 
        };
        
        const data = await api.fetchRecommendations(payload);
        let rawCourses = (data.courses || []).map(c => utils.normalizeCourse ? utils.normalizeCourse(c) : c);
        
        const uniqueCourses = [];
        const seen = new Set();
        rawCourses.forEach(c => {
            const code = String(c.課程代碼 || '').trim();
            const serial = String(c.序號 || '').trim();
            let key = '';
            if (code && serial) key = `${code}_${serial}`;
            else key = `${String(c.課程名稱).trim()}_${String(c.教師姓名).trim()}_${c.星期}_${c.起始節次}`;
            if (!seen.has(key)) {
                seen.add(key);
                uniqueCourses.push(c);
            }
        });
        let courses = uniqueCourses;

        if (['核心通識', '精進中文', '精進英外文', '教育學程', '大二體育', '大三、四體育'].includes(category)) {
            courses = courses.filter(c => {
                const classType = c['開課班別(代表)'] || c.開課班別 || '';
                return classType.includes(category);
            });
            if (category === '核心通識' && userCollege) {
                courses = courses.filter(c => c.學院 !== userCollege);
            }
        }
        else if (category === '系外選修') {
            courses = courses.filter(c => {
                const matchCollege = !searchCollege || c.學院 === searchCollege;
                const matchDept = !searchDept || c.科系 === searchDept;
                const matchGrade = !searchGrade || c.年級 === searchGrade;
                return matchCollege && matchDept && matchGrade;
            });
        }

        const dayMap = {'1':'一', '2':'二', '3':'三', '4':'四', '5':'五', '6':'六', '7':'日'};
        courses = courses.filter(course => {
            const cDay = String(course.星期);
            const isMatchNumeric = selectedDays.includes(cDay);
            const isMatchChinese = selectedDays.some(d => dayMap[d] === cDay);
            return isMatchNumeric || isMatchChinese;
        });

        if (emptySlotsOnly) {
            courses = courses.filter(course => {
                const check = utils.checkTimeConflict(course);
                return !check.hasConflict; 
            });
        }

        state.recommendedCourses = courses;
        ui.renderRecommendResults(state.recommendedCourses);
        
        if (courses.length > 0) {
             ui.showAlert(`為您找到 ${state.recommendedCourses.length} 門推薦課程`, 'success');
        } else {
             ui.showAlert('沒有找到符合條件的課程，請嘗試放寬條件', 'warning');
        }

    } catch (error) {
        console.error(error);
        ui.showAlert(error.message || '推薦失敗，請稍後再試', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-search me-2"></i> 開始推薦';
    }
}

async function handleSearchHistory() {
    const query = document.getElementById('search-history-input').value.trim();
    if (!query) {
        ui.showAlert('請輸入搜尋關鍵字', 'warning');
        return;
    }
    const btn = document.getElementById('btn-search-history');
    const input = document.getElementById('search-history-input');
    btn.disabled = true;
    input.disabled = true;
    const originalBtnContent = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>搜尋中...';
    
    try {
        const data = await api.fetchHistory(query);
        displayHistoryResults(data.courses || [], query);
    } catch (error) {
        console.error(error);
        ui.showAlert('搜尋失敗，請稍後再試', 'danger');
    } finally {
        btn.disabled = false;
        input.disabled = false;
        btn.innerHTML = originalBtnContent;
    }
}

function openHistoryModal(index) {
    const group = historyGroupsCache[index];
    if (!group) return;

    document.getElementById('historyDetailTitle').textContent = group.name;
    document.getElementById('historyDetailSubtitle').textContent = `主要教師：${group.teacher} | ${group.dept}`;

    const sortedForChart = [...group.data].sort((a, b) => {
        if (a.學年度 !== b.學年度) return a.學年度 - b.學年度;
        return a.學期 - b.學期;
    });

    renderHistoryChart(sortedForChart);

    const sortedForList = [...group.data].sort((a, b) => {
        if (b.學年度 !== a.學年度) return b.學年度 - a.學年度;
        return b.學期 - a.學期;
    });

    const tbody = document.getElementById('historyDetailTableBody');
    const tableElement = document.querySelector('#historyDetailModal table');
    if (tableElement) {
        tableElement.innerHTML = `
            <thead class="table-light">
                <tr class="text-nowrap">
                    <th class="ps-3">學年度</th>
                    <th>教師</th>
                    <th>開課班別</th>
                    <th>時間地點</th>
                    <th class="text-center">人數 / 上限</th>
                    <th class="text-end pe-3">大綱</th>
                </tr>
            </thead>
            <tbody id="historyDetailTableBody"></tbody>
        `;
    }
    const newTbody = document.getElementById('historyDetailTableBody');
    
    newTbody.innerHTML = sortedForList.map(c => {
        const enrolled = c.選上人數 || 0;
        const capacity = c.上限人數 || 0;
        const rate = capacity > 0 ? Math.round((enrolled / capacity) * 100) : 0;
        
        const syllabusUrl = c.教學大綱連結 || c['教學大綱連結'];
        const syllabusBtn = (syllabusUrl && syllabusUrl.includes('http'))
            ? `<a href="${syllabusUrl}" target="_blank" class="btn btn-sm btn-outline-secondary">
                 <i class="fas fa-external-link-alt"></i>
               </a>`
            : `<span class="text-muted small">-</span>`;

        const statusBadge = rate >= 100 
            ? `<span class="badge bg-danger rounded-pill">${enrolled}/${capacity}</span>`
            : `<span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 rounded-pill">${enrolled}/${capacity}</span>`;

        const teachers = c.教師列表 || c.教師姓名 || '';

        return `
            <tr>
                <td class="ps-3"><span class="fw-bold">${c.學年度}</span>-${c.學期}</td>
                <td class="small text-muted" style="max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${teachers}">
                    ${teachers}
                </td>
                <td>${c['開課班別(代表)'] || c.開課班別 || '-'}</td>
                <td class="small text-muted">
                    <div>週${c.星期 || '?'} ${c.起始節次 || ''}-${c.結束節次 || ''}節</div>
                    <div>${c.上課地點 || ''}</div>
                </td>
                <td class="text-center">${statusBadge}</td>
                <td class="text-end pe-3">${syllabusBtn}</td>
            </tr>
        `;
    }).join('');

    const modal = new bootstrap.Modal(document.getElementById('historyDetailModal'));
    modal.show();
}

function renderHistoryChart(data) {
    const ctx = document.getElementById('historyDetailChart').getContext('2d');
    if (historyChartInstance) {
        historyChartInstance.destroy();
    }
    const labels = data.map(d => `${d.學年度}-${d.學期}`);
    const enrolledData = data.map(d => d.選上人數 || 0);
    const capacityData = data.map(d => d.上限人數 || 0);

    historyChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '選上人數',
                    data: enrolledData,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#0d6efd',
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: '人數上限',
                    data: capacityData,
                    borderColor: '#dc3545',
                    borderDash: [5, 5],
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    titleColor: '#000',
                    bodyColor: '#666',
                    borderColor: '#ddd',
                    borderWidth: 1
                }
            },
            scales: {
                y: { beginAtZero: true, grid: { borderDash: [2, 2] } },
                x: { grid: { display: false } }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

// function displayHistoryResults(courses, query) {
//     const container = document.getElementById('history-results-container');
//     const title = document.getElementById('history-search-title');
//     const count = document.getElementById('history-result-count');

//     const uniqueCourses = [];
//     const seen = new Set();
//     (courses || []).forEach(c => {
//         const year = String(c.學年度 || '').trim();
//         const sem = String(c.學期 || '').trim();
//         const code = String(c.課程代碼 || '').trim();
//         const serial = String(c.序號 || '').trim();
//         const key = `${year}_${sem}_${code}_${serial}`;
//         if (!seen.has(key)) {
//             seen.add(key);
//             uniqueCourses.push(c);
//         }
//     });

//     if (title) title.textContent = `搜尋結果："${query}"`;
//     if (count) count.textContent = `共 ${uniqueCourses.length} 筆開課紀錄`;

//     if (!uniqueCourses || uniqueCourses.length === 0) {
//         if (container) container.innerHTML = '<div class="col-12 text-center text-muted py-5">沒有找到相關資料</div>';
//         return;
//     }

//     const groups = {};
//     uniqueCourses.forEach(c => {
//         const name = c.課程名稱 || c.中文課程名稱;
//         const teacher = c.教師姓名;
//         const key = `${name}_${teacher}`; 
        
//         if (!groups[key]) {
//             groups[key] = {
//                 name: name,
//                 teacher: teacher,
//                 dept: c.科系 || '',
//                 data: []
//             };
//         }
//         groups[key].data.push(c);
//     });

//     historyGroupsCache = Object.values(groups);

//     if (container) {
//         container.innerHTML = historyGroupsCache.map((group, index) => {
//             let sumRatio = 0;
//             let validCount = 0;

//             group.data.forEach(item => {
//                 const registered = parseFloat(item.登記人數 || 0);
//                 if (registered > 0) {
//                     let ratio = 50 / registered;
//                     if (ratio > 1) ratio = 1;
//                     sumRatio += ratio;
//                     validCount++;
//                 }
//             });

//             const avgRate = validCount > 0 ? (sumRatio / validCount) : 0;
//             const avgRatePercent = (avgRate * 100).toFixed(0);
            
//             let badgeHtml = '';
//             if (validCount > 0) {
//                 const badgeClass = avgRate < 0.5 ? 'bg-danger' : 'bg-success'; 
//                 const icon = avgRate < 0.5 ? '<i class="fas fa-fire me-1"></i>' : '';
                
//                 badgeHtml = `
//                     <span class="badge ${badgeClass} p-2" 
//                           title="歷年平均選上率: ${avgRatePercent}% (採計 ${validCount} 筆資料)\n公式: 50 / 登記人數 (上限 100%)">
//                         ${icon}選上率 ${avgRatePercent}%
//                     </span>`;
//             } else {
//                 badgeHtml = `<span class="badge bg-light text-muted border p-2">無選上率資料</span>`;
//             }

//             const latest = group.data.sort((a, b) => {
//                 if (b.學年度 !== a.學年度) return b.學年度 - a.學年度;
//                 return b.學期 - a.學期;
//             })[0];

//             return `
//                 <div class="col-md-6 col-lg-4">
//                     <div class="card h-100 shadow-sm border-0 hover-shadow transition-all" 
//                          style="cursor: pointer;" 
//                          onclick="openHistoryModal(${index})">
//                         <div class="card-body d-flex flex-column">
//                             <div class="d-flex justify-content-between align-items-start mb-2">
//                                 <span class="badge bg-primary bg-opacity-10 text-primary">${group.dept}</span>
//                                 <span class="badge rounded-pill bg-light text-dark border">${group.data.length} 次開課</span>
//                             </div>
                            
//                             <h5 class="card-title fw-bold text-dark mb-1 text-truncate" title="${group.name}">
//                                 ${group.name}
//                             </h5>
                            
//                             <p class="card-text text-muted small mb-3">
//                                 <i class="fas fa-chalkboard-teacher me-1"></i> ${group.teacher}
//                             </p>
                            
//                             <div class="mt-auto pt-3 border-top">
//                                 <div class="d-flex justify-content-between align-items-center">
//                                     ${badgeHtml}
//                                     <small class="text-muted">
//                                         最近: ${latest.學年度}-${latest.學期} <i class="fas fa-chevron-right ms-1"></i>
//                                     </small>
//                                 </div>
//                             </div>
//                         </div>
//                     </div>
//                 </div>
//             `;
//         }).join('');
//     }
// }









//fix
function displayHistoryResults(courses, query) {
    const container = document.getElementById('history-results-container');
    const title = document.getElementById('history-search-title');
    const count = document.getElementById('history-result-count');

    // 1. 去重邏輯
    const uniqueCourses = [];
    const seen = new Set();
    (courses || []).forEach(c => {
        const year = String(c.學年度 || '').trim();
        const sem = String(c.學期 || '').trim();
        const code = String(c.課程代碼 || '').trim();
        const serial = String(c.序號 || '').trim();
        const key = `${year}_${sem}_${code}_${serial}`;
        if (!seen.has(key)) {
            seen.add(key);
            uniqueCourses.push(c);
        }
    });

    if (title) title.textContent = `搜尋結果："${query}"`;
    if (count) count.textContent = `共 ${uniqueCourses.length} 筆開課紀錄`;

    if (!uniqueCourses || uniqueCourses.length === 0) {
        if (container) container.innerHTML = '<div class="col-12 text-center text-muted py-5">沒有找到相關資料</div>';
        return;
    }

    // 2. 分群邏輯
    const groups = {};
    uniqueCourses.forEach(c => {
        const name = c.課程名稱 || c.中文課程名稱;
        const teacher = c.教師姓名;
        const key = `${name}_${teacher}`; 
        
        if (!groups[key]) {
            groups[key] = {
                name: name,
                teacher: teacher,
                dept: c.科系 || '',
                data: []
            };
        }
        groups[key].data.push(c);
    });

    // 取得分群後的陣列
    historyGroupsCache = Object.values(groups);

    // 3. 排序邏輯：先按中籤率(低到高)，再按飽和度(高到低)
    historyGroupsCache.sort((a, b) => {
        const getStats = (group) => {
            let sRateSum = 0, sSatSum = 0, vCount = 0;
            group.data.forEach(item => {
                const reg = parseFloat(item.登記人數 || 0);
                const limit = parseFloat(item.人數上限 || 50);
                const accepted = parseFloat(item.選上人數 || Math.min(reg, limit)); // 若無欄位則取上限

                if (reg > 0) {
                    sRateSum += (accepted / reg); // 選上人數 / 登記人數
                    sSatSum += (reg / limit);     // 登記人數 / 人數上限
                    vCount++;
                }
            });
            return {
                rate: vCount > 0 ? (sRateSum / vCount) : 999, // 無資料排最後
                sat: vCount > 0 ? (sSatSum / vCount) : -1
            };
        };

        const statsA = getStats(a);
        const statsB = getStats(b);

        if (statsA.rate !== statsB.rate) {
            return statsA.rate - statsB.rate; // 中籤率低到高 (衡量選課難度)
        }
        return statsB.sat - statsA.sat; // 飽和度高到低 (衡量熱門程度)
    });

    // 4. 渲染邏輯
    if (container) {
        container.innerHTML = historyGroupsCache.map((group, index) => {
            let sumRate = 0;
            let sumSaturation = 0;
            let validCount = 0;

            group.data.forEach(item => {
                const reg = parseFloat(item.登記人數 || 0);
                const limit = parseFloat(item.人數上限 || 50);
                const accepted = parseFloat(item.選上人數 || Math.min(reg, limit));

                if (reg > 0) {
                    sumRate += (accepted / reg);
                    sumSaturation += (reg / limit);
                    validCount++;
                }
            });

            // 選上率計算 (中籤率)
            const avgRate = validCount > 0 ? (sumRate / validCount) : 0;
            const avgRatePercent = (avgRate * 100).toFixed(0);
            
            // 飽和度計算
            const avgSat = validCount > 0 ? (sumSaturation / validCount) : 0;
            const avgSatPercent = (avgSat * 100).toFixed(0);
            
            let badgesHtml = '';
            if (validCount > 0) {
                // 中籤率樣式 (衡難度)
                const rateClass = avgRate < 0.3 ? 'bg-danger' : (avgRate < 0.6 ? 'bg-warning text-dark' : 'bg-success'); 
                const rateIcon = avgRate < 0.3 ? '<i class="fas fa-exclamation-triangle me-1"></i>' : '<i class="bi bi-dice-5 me-1"></i>';
                
                // 飽和度樣式 (衡熱門)
                const satClass = avgSat >= 1.5 ? 'bg-danger' : (avgSat >= 1.0 ? 'bg-primary' : 'bg-info text-white');

                badgesHtml = `
                    <div class="d-flex flex-wrap gap-1 mt-2">
                        <span class="badge ${rateClass} p-2" 
                              title="歷年平均中籤率: ${avgRatePercent}% (衡量選課難度)\n公式: 選上人數 / 登記人數">
                            ${rateIcon}中籤率 ${avgRatePercent}%
                        </span>
                        <span class="badge ${satClass} p-2" 
                              title="歷年平均飽和度: ${avgSatPercent}% (衡量熱門程度)\n公式: 登記人數 / 上限人數">
                            <i class="bi bi-people-fill me-1"></i>飽和度 ${avgSatPercent}%
                        </span>
                    </div>`;
            } else {
                badgesHtml = `<span class="badge bg-light text-muted border p-2 mt-2">無選上紀錄資料</span>`;
            }

            // 取得最新一筆資料
            const latest = group.data.sort((a, b) => {
                const yearA = parseInt(a.學年度 || 0);
                const yearB = parseInt(b.學年度 || 0);
                if (yearB !== yearA) return yearB - yearA;
                return (b.學期 || 0) - (a.學期 || 0);
            })[0];

            return `
                <div class="col-md-6 col-lg-4 mb-4">
                    <div class="card h-100 shadow-sm border-0 hover-shadow transition-all" 
                         style="cursor: pointer;" 
                         onclick="openHistoryModal(${index})">
                        <div class="card-body d-flex flex-column">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge bg-primary bg-opacity-10 text-primary">${group.dept}</span>
                                <span class="badge rounded-pill bg-light text-dark border">${group.data.length} 次開課</span>
                            </div>
                            
                            <h5 class="card-title fw-bold text-dark mb-1 text-truncate" title="${group.name}">
                                ${group.name}
                            </h5>
                            
                            <p class="card-text text-muted small mb-3">
                                <i class="fas fa-chalkboard-teacher me-1"></i> ${group.teacher}
                            </p>
                            
                            <div class="mt-auto pt-3 border-top">
                                <div class="d-flex flex-column gap-2">
                                    ${badgesHtml}
                                    <div class="d-flex justify-content-end">
                                        <small class="text-muted">
                                            最近: ${latest.學年度 || '?'}-${latest.學期 || '?'} <i class="fas fa-chevron-right ms-1"></i>
                                        </small>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }
}
//fix end






function exposeGlobalFunctions() {
    window.switchTab = ui.switchTab;
    
    window.toggleSidebar = () => {
        const sidebar = document.querySelector('.sidebar');
        const backdrop = document.getElementById('sidebarBackdrop');
        const toggles = document.querySelectorAll('.sidebar-toggle');
        const isOpen = sidebar.classList.toggle('show');
        if (backdrop) {
            if (isOpen) {
                backdrop.classList.add('show');
                backdrop.setAttribute('aria-hidden', 'false');
            } else {
                backdrop.classList.remove('show');
                backdrop.setAttribute('aria-hidden', 'true');
            }
        }
        toggles.forEach(btn => btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false'));
    };

    window.toggleScheduleView = (mode) => {
        const section = document.getElementById('tab-schedule');
        if (!section) return;
        section.setAttribute('data-view', mode);

        if (mode === 'auto') localStorage.removeItem('scheduleViewPref');
        else localStorage.setItem('scheduleViewPref', mode);

        const btnTable = document.getElementById('view-table-btn');
        const btnCards = document.getElementById('view-cards-btn');
        if (btnTable && btnCards) {
            if (mode === 'table') {
                btnTable.classList.add('active'); btnTable.setAttribute('aria-pressed','true');
                btnCards.classList.remove('active'); btnCards.setAttribute('aria-pressed','false');
            } else if (mode === 'cards') {
                btnCards.classList.add('active'); btnCards.setAttribute('aria-pressed','true');
                btnTable.classList.remove('active'); btnTable.setAttribute('aria-pressed','false');
            } else {
                btnTable.classList.remove('active'); btnTable.setAttribute('aria-pressed','false');
                btnCards.classList.remove('active'); btnCards.setAttribute('aria-pressed','false');
            }
        }
        ui.updateScheduleDisplay();
        if (mode === 'table') ui.showAlert('已切換為表格檢視', 'info');
        else if (mode === 'cards') ui.showAlert('已切換為卡片檢視', 'info');
    }; 
    
    window.removeCourse = (code, serial) => {
        const sCode = String(code);
        const sSerial = String(serial);
        const course = state.selectedCourses.find(c => 
            String(c.課程代碼) === sCode && 
            String(c.序號) === sSerial
        );
        const courseName = course ? (course.課程名稱 || course.中文課程名稱) : '此課程';
        Swal.fire({
            title: `確定要移除「${courseName}」嗎？`,
            text: "移除後將無法復原，需重新加入",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: '確定移除',
            confirmButtonColor: '#dc3545', 
            cancelButtonText: '取消',
            cancelButtonColor: '#6c757d',
            reverseButtons: true 
        }).then((result) => {
            if (result.isConfirmed) {
                if (utils.removeCourseFromState(code, serial)) {
                    ui.updateScheduleDisplay();
                    ui.updateSelectedCoursesList();
                    saveToLocalStorage();
                    ui.showAlert('課程已移除', 'info');
                }
            }
        });
    };
    window.showCourseDetail = (course) => ui.showCourseDetailModal(course);
    window.showCourseDetailModal = (index) => { if (state.recommendedCourses[index]) ui.showCourseDetailModal(state.recommendedCourses[index]); };
    window.showSelectedCourseDetail = (code, serial) => {
        const sCode = String(code);
        const sSerial = String(serial);
        const course = state.selectedCourses.find(c => 
            String(c.課程代碼) === sCode && 
            String(c.序號) === sSerial
        );
        if (course) {
            ui.showCourseDetailModal(course);
        }
    };
    window.addRecommendedCourse = (course) => {
        const result = utils.addCourseToState(course);
        if (result === true) {
            ui.updateScheduleDisplay();
            ui.updateSelectedCoursesList();
            saveToLocalStorage();
            const rawTotal = state.selectedCourses.reduce((sum, c) => sum + (parseFloat(c.學分) || 0), 0);
            const target = parseFloat(document.getElementById('range-credits').value) || 0;
            if (rawTotal > target) {
                 ui.showAlert(`課程已加入，但總學分(${rawTotal})已超過目標(${target})`, 'warning');
            } else {
                 ui.showAlert('課程已加入', 'success');
            }
        } else if (result === 'conflict') {
            ui.showAlert('時間衝突：該時段已有課程', 'warning');
        } else {
            ui.showAlert('該課程已在您的課表中', 'info');
        }
    };
    window.addRecommendedCourseByIndex = (index) => { if (state.recommendedCourses[index]) window.addRecommendedCourse(state.recommendedCourses[index]); };
    window.openHistoryModal = openHistoryModal;
}

function debounce(fn, wait = 150) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
}

function detectAndApplyScheduleView() {
    const section = document.getElementById('tab-schedule');
    if (!section) return;
    const pref = localStorage.getItem('scheduleViewPref');
    if (pref === 'table' || pref === 'cards') {
        section.setAttribute('data-view', pref);
    } else {
        if (section.getAttribute('data-view') === 'auto') {
            section.setAttribute('data-view', window.innerWidth < 768 ? 'cards' : 'table');
        }
    }
    ui.updateScheduleDisplay();
}

function setupEventListeners() {
    document.addEventListener('click', e => {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar.classList.contains('show') && !sidebar.contains(e.target) && !e.target.closest('.sidebar-toggle')) {
            sidebar.classList.remove('show');
            const backdrop = document.getElementById('sidebarBackdrop');
            if (backdrop) backdrop.classList.remove('show');
        }
    });

    document.getElementById('btn-import').addEventListener('click', handleImportCourses);
    document.getElementById('btn-clear').addEventListener('click', handleClearSchedule);
    document.getElementById('btn-search-recommend').addEventListener('click', handleSearchRecommend);
    document.getElementById('btn-search-history').addEventListener('click', handleSearchHistory);
    document.getElementById('search-history-input').addEventListener('keypress', e => {
        if (e.key === 'Enter') handleSearchHistory();
    });

    document.getElementById('select-year').addEventListener('change', function() {
        state.currentYear = parseInt(this.value);
        loadCoursesData();
    });
    document.getElementById('select-semester').addEventListener('change', function() {
        state.currentSemester = parseInt(this.value);
        loadCoursesData();
    });

    document.getElementById('select-college').addEventListener('change', function() {
        loadDepartmentsByCollege(this.value, 'select-dept-recommend');
    });

    const updateGradeHandler = () => {
        const college = document.getElementById('select-college-schedule').value;
        const dept = document.getElementById('select-department-schedule').value;
        const sys = document.getElementById('select-system-schedule').value;
        const lvl = document.getElementById('select-level-schedule').value;
        
        document.getElementById('select-grade-schedule').innerHTML = '<option value="">選擇年級</option>';
        document.getElementById('select-class-schedule').innerHTML = '<option value="">選擇班級</option>';

        if (college && dept) {
            updateGradeList(college, dept, sys, lvl);
        }
    };

    document.getElementById('select-system-schedule').addEventListener('change', updateGradeHandler);
    document.getElementById('select-level-schedule').addEventListener('change', updateGradeHandler);
    
    document.getElementById('select-college-schedule').addEventListener('change', function() {
        loadDepartmentsByCollege(this.value, 'select-department-schedule');
        document.getElementById('select-grade-schedule').innerHTML = '<option value="">選擇年級</option>';
        document.getElementById('select-class-schedule').innerHTML = '<option value="">選擇班級</option>';
    });

    document.getElementById('select-department-schedule').addEventListener('change', updateGradeHandler);

    document.getElementById('select-grade-schedule').addEventListener('change', function() {
        const college = document.getElementById('select-college-schedule').value;
        const dept = document.getElementById('select-department-schedule').value;
        const sys = document.getElementById('select-system-schedule').value;
        const lvl = document.getElementById('select-level-schedule').value;
        const grade = this.value;
        if (college && dept && grade) {
            updateClassList(college, dept, sys, lvl, grade);
        }
    });

    const rangeCredits = document.getElementById('range-credits');
    if (rangeCredits) {
        rangeCredits.addEventListener('input', function() {
            document.getElementById('target-credits').textContent = this.value;
        });
    }
    
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.category-btn').forEach(b => {
                b.classList.remove('active', 'btn-primary');
                b.classList.add('btn-outline-primary');
            });
            this.classList.remove('btn-outline-primary');
            this.classList.add('active', 'btn-primary');
            handleSearchRecommend();
        });
    });
}
