import { WEEKDAYS, WEEKDAY_MAP, PERIOD_TIMES, PERIOD_ORDER } from './config.js';
import { state } from './state.js';
import { checkTimeConflict } from './utils.js';

export function showAlert(message, type = 'info') {
    const iconMap = { info: 'info', success: 'success', warning: 'warning', danger: 'error', error: 'error' };
    const icon = iconMap[type] || type;
    Swal.fire({
        toast: true,
        position: 'top-end',
        icon: icon,
        title: message,
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
    });
}

export function initializeScheduleTable() {
    const container = document.getElementById('schedule-table');
    let html = '<table class="schedule-table table-bordered"><thead><tr><th>節次</th>';
    for (let day of WEEKDAYS) html += `<th>週${day}</th>`;
    html += '</tr></thead><tbody>';
    
    for (let period of PERIOD_ORDER) {
        const timeStr = PERIOD_TIMES[period] || '';
        const label = period === 14 ? '中午' : `第${period}節`;
        
        html += `<tr><td class="time-cell">
                    <div class="fw-bold">${label}</div>
                    <div class="small text-muted" style="font-size: 0.75rem;">${timeStr}</div>
                 </td>`;
        for (let day of WEEKDAYS) {
            html += `<td class="schedule-cell-empty" data-day="${WEEKDAY_MAP[day]}" data-period="${period}"></td>`;
        }
        html += '</tr>';
    }
    html += '</tbody></table>';
    container.innerHTML = html;
}

export function updateScheduleDisplay() {
    document.querySelectorAll('td[data-day][data-period]').forEach(cell => {
        cell.innerHTML = '';
        cell.className = 'schedule-cell-empty'; 
        cell.style.display = '';              
        cell.removeAttribute('rowspan');
        cell.onclick = null;
    });
    
    state.selectedCourses.forEach(course => {
        const day = WEEKDAY_MAP[course.星期] || parseInt(course.星期);
        const startPeriod = parseInt(course.起始節次);
        const endPeriod = parseInt(course.結束節次);
        
        if (day && startPeriod && endPeriod) {
            const coveredPeriods = [];
            for (let p = startPeriod; p <= endPeriod; p++) {
                coveredPeriods.push(p);
            }
            
            const groups = [];
            let currentGroup = [];
            
            coveredPeriods.forEach(p => {
                const pIndex = PERIOD_ORDER.indexOf(p);
                if (pIndex === -1) return;
                
                if (currentGroup.length === 0) {
                    currentGroup.push(p);
                } else {
                    const lastP = currentGroup[currentGroup.length - 1];
                    const lastIndex = PERIOD_ORDER.indexOf(lastP);
                    if (pIndex === lastIndex + 1) {
                        currentGroup.push(p);
                    } else {
                        groups.push(currentGroup);
                        currentGroup = [p];
                    }
                }
            });
            if (currentGroup.length > 0) groups.push(currentGroup);

            groups.forEach(group => {
                const firstP = group[0];
                const span = group.length;
                const cell = document.querySelector(`td[data-day="${day}"][data-period="${firstP}"]`);
                
                if (cell) {
                    cell.rowSpan = span;
                    
                    let courseType = 'course-elective';
                    if (course.課程性質?.includes('必修')) courseType = 'course-required';
                    else if (course.課程性質?.match(/通識/)) courseType = 'course-general';
                    else if (course.課程性質?.match(/國文|英文/)) courseType = 'course-language';
                    
                    cell.className = `schedule-cell ${courseType}`;
                    cell.innerHTML = `
                        <div class="course-name">${course.課程名稱 || course.中文課程名稱 || ''}</div>
                        <div class="course-teacher">${course.教師姓名 || ''}</div>
                        <div class="course-info">${course.上課地點 || ''}</div>
                    `;
                    
                    cell.onclick = () => window.showCourseDetail(course);
                    
                    for (let i = 1; i < group.length; i++) {
                        const nextP = group[i];
                        const nextCell = document.querySelector(`td[data-day="${day}"][data-period="${nextP}"]`);
                        if (nextCell) nextCell.style.display = 'none';
                    }
                }
            });
        }
    });

    renderScheduleCards();
}

export function renderScheduleCards() {
    const container = document.getElementById('schedule-cards');
    if(!container) return;

    if (state.selectedCourses.length === 0) {
        container.innerHTML = `<div class="text-center text-muted py-4">尚未選擇任何課程</div>`;
        return;
    }

    const grouped = {};
    state.selectedCourses.forEach(course => {
        let day = course.星期 || '0';
        if (/^\d+$/.test(String(day))) {
            const map = { '1':'一','2':'二','3':'三','4':'四','5':'五','6':'六','7':'日' };
            day = map[String(day)] || String(day);
        }
        if (!grouped[day]) grouped[day] = [];
        grouped[day].push(course);
    });

    const days = Object.keys(grouped).sort((a,b)=> {
        const aIdx = WEEKDAYS.indexOf(a) === -1 ? 99 : WEEKDAYS.indexOf(a);
        const bIdx = WEEKDAYS.indexOf(b) === -1 ? 99 : WEEKDAYS.indexOf(b);
        return aIdx - bIdx;
    });

    const html = days.map(day => {
        const courses = grouped[day].sort((a,b)=>parseInt(a.起始節次) - parseInt(b.起始節次));
        const dayLabel = `週${day}`;
        const list = courses.map(course => `
            <div class="card course-card">
                <div class="card-body d-flex justify-content-between align-items-start">
                    <div>
                        <div class="course-time">${course.起始節次}-${course.結束節次}節</div>
                        <div class="fw-bold text-truncate">${course.課程名稱 || course.中文課程名稱 || ''}</div>
                        <div class="course-meta small text-muted">${course.教師姓名 || ''} • ${course.學分 || 0} 學分</div>
                        <div class="course-meta small text-muted">${course.上課地點 || ''}</div>
                    </div>
                    <div class="d-flex flex-column gap-2 ms-3">
                        <button class="btn btn-sm btn-outline-primary" onclick="showSelectedCourseDetail('${course.課程代碼}','${course.序號}')">詳情</button>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeCourse('${course.課程代碼}', '${course.序號}')">移除</button>
                    </div>
                </div>
            </div>
        `).join('');

        return `
            <div class="day-group">
                <div class="day-header">${dayLabel}</div>
                ${list}
            </div>
        `;
    }).join('');

    container.innerHTML = html;
}

export function updateSelectedCoursesList() {
    const container = document.getElementById('selected-courses-list');
    
    const rawTotal = state.selectedCourses.reduce((sum, c) => sum + (parseFloat(c.學分) || 0), 0);
    const totalCredits = Number.isInteger(rawTotal) ? rawTotal : rawTotal.toFixed(1);
    
    const targetInput = document.getElementById('range-credits');
    const target = targetInput ? (parseFloat(targetInput.value) || 0) : 0;
    
    const isOver = target > 0 && rawTotal > target;

    const updateElement = (id) => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = totalCredits;
            if (isOver) {
                el.classList.add('text-danger', 'fw-bold'); 
            } else {
                el.classList.remove('text-danger', 'fw-bold');
            }
        }
    };

    updateElement('total-credits');
    updateElement('current-credits');
    
    if (state.selectedCourses.length === 0) {
        container.innerHTML = '<div class="col-12 text-center text-muted py-4">尚未選擇任何課程</div>';
        return;
    }
    
    container.innerHTML = state.selectedCourses.map(course => `
        <div class="col-md-6 col-lg-4">
            <div class="card course-card h-100">
                <div class="card-body">
                    <h6 class="card-title">${course.課程名稱 || course.課程名稱}</h6>
                    <p class="card-text small text-muted mb-2">${course.教師姓名 || ''} • ${course.學分 || 0} 學分</p>
                    <p class="card-text small text-muted mb-2"><i class="fas fa-university me-1"></i>${course.學院 || ''} ${course.科系 || ''}</p>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeCourse('${course.課程代碼}', '${course.序號}')">
                        <i class="fas fa-trash me-1"></i>移除
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

export function renderRecommendResults(courses) {
    const container = document.getElementById('recommend-courses-grid');
    if (courses.length === 0) {
        container.innerHTML = '<div class="col-12 text-center text-muted py-5">沒有找到符合條件的課程</div>';
        return;
    }
    
    container.innerHTML = courses.map((course, index) => {
        let saturationHtml = '';
        if (course.historical_acceptance_rate != null) {
            const satRate = parseFloat(course.historical_acceptance_rate);
            const satPercent = (satRate * 100).toFixed(0);
            const badgeClass = satRate < 0.5 ? 'bg-danger' : 'bg-success'; 
            const icon = satRate < 0.5 ? '<i class="fas fa-fire me-1"></i>' : '';
            
            saturationHtml = `
                <span class="badge ${badgeClass} border border-white shadow-sm" title="歷年平均選上率: ${satPercent}% (排除登記=0)">
                    ${icon}選上率 ${satPercent}%
                </span>`;
        } else {
            saturationHtml = `<span class="badge bg-light text-muted border">無選上率資料</span>`;
        }
        
        const countHtml = `<small class="text-muted ms-auto"><i class="fas fa-user-friends me-1"></i>${course.選上人數}/${course.上限人數}</small>`;
        const isConflict = checkTimeConflict(course).hasConflict;
        const time = (course.星期 && course.起始節次) ? `週${course.星期} ${course.起始節次}-${course.結束節次}節` : '時間未定';

        return `
            <div class="col-md-6 col-lg-4">
                <div class="card course-card h-100 ${isConflict ? 'border-danger' : 'border-0 shadow-sm'}">
                    ${isConflict ? '<div class="position-absolute top-0 start-0 m-2"><span class="badge bg-danger">衝堂</span></div>' : ''}
                    
                    <div class="card-body d-flex flex-column p-3">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <span class="badge bg-primary bg-opacity-10 text-primary">${course.學分}學分</span>
                            ${saturationHtml}
                        </div>

                        <h5 class="card-title fw-bold text-dark mb-1 text-truncate" title="${course.課程名稱}">
                            <span class="text-secondary fw-normal me-1" style="font-size: 0.9em;">${course.課程代碼}</span>
                            ${course.課程名稱 || course.中文課程名稱}
                        </h5>
                        <div class="small text-muted mb-3">
                            ${course.教師姓名} <span class="mx-1">•</span> ${course.科系 || ''}
                        </div>
                        
                        <div class="mt-auto">
                            <div class="d-flex align-items-center mb-3 text-secondary small">
                                <i class="far fa-clock me-2"></i> ${time}
                                ${countHtml}
                            </div>
                            
                            <div class="d-flex gap-2">
                                <button class="btn btn-sm btn-outline-primary flex-grow-1" onclick='showCourseDetailModal(${index})'>詳情</button>
                                ${isConflict 
                                    ? `<button class="btn btn-sm btn-secondary flex-grow-1" disabled>衝堂</button>` 
                                    : `<button class="btn btn-sm btn-primary flex-grow-1" onclick='addRecommendedCourseByIndex(${index})'>加入</button>`
                                }
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

export function showCourseDetailModal(course) {
    const modalElement = document.getElementById('courseDetailModal');
    
    const modalDialog = modalElement.querySelector('.modal-dialog');
    if (modalDialog) {
        modalDialog.classList.remove('modal-lg');
        modalDialog.classList.remove('modal-xl');
    }

    const modal = new bootstrap.Modal(modalElement);
    document.getElementById('courseDetailTitle').textContent = course.課程名稱 || course.中文課程名稱;
    
    const body = document.getElementById('courseDetailBody');
    
    const syllabusUrl = course.教學大綱連結 || course['教學大綱連結'];
    const syllabusLinkHtml = (syllabusUrl && syllabusUrl.includes('http')) 
        ? `<a href="${syllabusUrl}" target="_blank" class="btn btn-sm btn-outline-primary w-100">
             <i class="fas fa-external-link-alt me-1"></i>查看教學大綱
           </a>` 
        : '<span class="text-muted small">無連結</span>';

    const enrolled = parseFloat(course.選上人數 || 0);
    const capacity = parseFloat(course.上限人數 || 0);
    let saturationPercent = 0;
    if (capacity > 0) {
        saturationPercent = Math.round((enrolled / capacity) * 100);
    }

    let satBadgeClass = 'bg-success';
    let satText = '名額充足';
    let satIcon = '<i class="fas fa-check-circle me-1"></i>';

    if (saturationPercent >= 100) {
        satBadgeClass = 'bg-danger';
        satText = '已額滿';
        satIcon = '<i class="fas fa-exclamation-circle me-1"></i>';
    } else if (saturationPercent >= 80) {
        satBadgeClass = 'bg-warning text-dark';
        satText = '即將額滿';
        satIcon = '<i class="fas fa-exclamation-triangle me-1"></i>';
    }

    const teacherDisplay = course.教師列表 || course.教師姓名 || '未定';

    body.innerHTML = `
        <div class="container-fluid p-0">
            <div class="row g-3">
                <div class="col-12">
                    <div class="text-muted small mb-1">課程代碼</div>
                    <div class="fw-bold text-dark border-bottom pb-2">${course.課程代碼 || '-'}</div>
                </div>

                <div class="col-12">
                    <div class="text-muted small mb-1">開課班別</div>
                    <div class="fw-bold text-dark border-bottom pb-2">${course['開課班別(代表)'] || course.開課班別 || '-'}</div>
                </div>

                <div class="col-12">
                    <div class="text-muted small mb-1">學分 / 性質</div>
                    <div class="border-bottom pb-2">
                        <span class="fs-5 fw-bold text-primary">${course.學分}</span> 學分
                        <span class="badge bg-secondary ms-2">${course.課程性質 || '選修'}</span>
                    </div>
                </div>

                <div class="col-12">
                    <div class="text-muted small mb-1">授課教師</div>
                    <div class="fw-bold border-bottom pb-2">${teacherDisplay}</div>
                </div>

                <div class="col-12">
                    <div class="text-muted small mb-1">上課時間</div>
                    <div class="border-bottom pb-2">
                        <i class="far fa-clock me-2 text-muted"></i>週${course.星期} 第 ${course.起始節次}-${course.結束節次} 節
                    </div>
                </div>

                <div class="col-12">
                    <div class="text-muted small mb-1">上課地點</div>
                    <div class="border-bottom pb-2">
                        <i class="fas fa-map-marker-alt me-2 text-muted"></i>${course.上課地點 || '未定'}
                    </div>
                </div>

                <div class="col-12">
                    <div class="text-muted small mb-1">選課狀況 (飽和度)</div>
                    <div class="border-bottom pb-2">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <div>
                                <span class="fw-bold fs-5">${enrolled}</span>
                                <span class="text-muted mx-1">/</span>
                                <span class="text-muted">${capacity} 人</span>
                            </div>
                            <span class="badge ${satBadgeClass} p-2">
                                ${satIcon} ${satText}
                            </span>
                        </div>
                        <div class="progress" style="height: 6px;">
                            <div class="progress-bar ${satBadgeClass}" role="progressbar" style="width: ${Math.min(saturationPercent, 100)}%" aria-valuenow="${saturationPercent}" aria-valuemin="0" aria-valuemax="100"></div>
                        </div>
                        <div class="text-end mt-1">
                            <small class="text-muted">飽和度 ${saturationPercent}%</small>
                        </div>
                    </div>
                </div>
                <div class="col-12">
                    <div class="text-muted small mb-1">課程大綱</div>
                    <div>${syllabusLinkHtml}</div>
                </div>

                ${course.備註 ? `
                <div class="col-12 mt-2">
                    <div class="alert alert-light border border-secondary border-opacity-25 mb-0 small">
                        <i class="fas fa-info-circle me-1 text-primary"></i>
                        <strong>備註：</strong> ${course.備註}
                    </div>
                </div>` : ''}
            </div>
        </div>
    `;
    
    const addBtn = document.getElementById('btn-add-to-schedule');
    if (addBtn) {
        const newBtn = addBtn.cloneNode(true);
        addBtn.parentNode.replaceChild(newBtn, addBtn);
        
        newBtn.onclick = () => {
            modal.hide();
            if (window.addRecommendedCourse) {
                window.addRecommendedCourse(course);
            }
        };
    }
    
    modal.show();
}

export function switchTab(tabId) {
    document.querySelectorAll('.page-section').forEach(s => s.classList.add('d-none'));
    const target = document.getElementById(tabId);
    if(target) target.classList.remove('d-none');
    
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    const activeBtn = Array.from(document.querySelectorAll('.nav-btn')).find(btn => 
        btn.getAttribute('onclick')?.includes(tabId)
    );
    if(activeBtn) activeBtn.classList.add('active');
}

export async function showConflictResolutionModal(newCourse, oldCourse) {
    const formatTime = (c) => `週${c.星期} ${c.起始節次}-${c.結束節次}節`;

    const result = await Swal.fire({
        title: '課程時間衝突',
        html: `
            <div class="mb-3">同一時段只能選擇一門課程，請選擇您要保留的課程：</div>
            <div class="row g-2">
                <div class="col-6">
                    <div class="card h-100 border-secondary">
                        <div class="card-header bg-secondary text-white small">原本的課程 (已在課表)</div>
                        <div class="card-body p-2 text-start">
                            <h6 class="card-title text-truncate mb-1" title="${oldCourse.課程名稱}">${oldCourse.課程名稱}</h6>
                            <p class="small text-muted mb-1">${oldCourse.教師姓名}</p>
                            <p class="small text-muted mb-0">${formatTime(oldCourse)}</p>
                        </div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="card h-100 border-primary">
                        <div class="card-header bg-primary text-white small">準備導入的新課程</div>
                        <div class="card-body p-2 text-start">
                            <h6 class="card-title text-truncate mb-1" title="${newCourse.課程名稱}">${newCourse.課程名稱}</h6>
                            <p class="small text-muted mb-1">${newCourse.教師姓名}</p>
                            <p class="small text-muted mb-0">${formatTime(newCourse)}</p>
                        </div>
                    </div>
                </div>
            </div>
        `,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '改選新課程',
        confirmButtonColor: '#0d6efd', 
        cancelButtonText: '保留原課程',
        cancelButtonColor: '#6c757d', 
        reverseButtons: true, 
        allowOutsideClick: false
    });

    return result.isConfirmed ? 'replace' : 'keep';
}