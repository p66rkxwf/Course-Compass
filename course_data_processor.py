from os import name
import pandas as pd
import re
from pathlib import Path
from datetime import datetime

def extract_year_semester_from_filename(filepath):
    """從檔名擷取學年度與學期"""
    filename = Path(filepath).name
    match = re.search(r'courses_(\d{3})_(\d)', filename)

    if not match:
        return None, None

    return match.group(1), match.group(2)

def split_course_name(name):
    """
    從字串尾端切分課程名稱：
    - 英文課名一定在最後
    - 中文課名允許包含英文字母、數字、括號
    """
    if pd.isna(name):
        return pd.Series([pd.NA, pd.NA])

    text = str(name).strip()
    if not text:
        return pd.Series([pd.NA, pd.NA])

    pattern = r'([A-Za-z][A-Za-z\s\-\(\)\[\]ⅠⅡⅢIVX0-9\.\',:]{5,})$'
    match = re.search(pattern, text)

    if not match:
        return pd.Series([text, pd.NA])

    en = match.group(1).strip()
    zh = text[:match.start()].strip(" ,，;；")

    return pd.Series([zh if zh else pd.NA, en])

def parse_schedule_location(schedule_str):
    """解析上課節次+地點，回傳 List of Dict 供 Explode 使用"""
    if pd.isna(schedule_str) or str(schedule_str).strip() == '未知':
        return [{'星期': pd.NA, '起始節次': pd.NA, '結束節次': pd.NA, '上課地點': pd.NA}]

    text = str(schedule_str).strip()
    pattern = r'(\([一二三四五六日]\))\s*([\d,\-]+)\s*(.*?)(?=\s*\([一二三四五六日]\)|$)'
    matches = re.findall(pattern, text)
    
    if not matches:
        return [{'星期': pd.NA, '起始節次': pd.NA, '結束節次': pd.NA, '上課地點': text}]
    
    results = []
    for w, t, l in matches:
        start_node = pd.NA
        end_node = pd.NA
        try:
            nums = re.findall(r'\d+', t)
            if nums:
                start_node = int(nums[0])
                end_node = int(nums[-1])
        except (ValueError, IndexError):
            pass
            
        results.append({
            '星期': w,
            '起始節次': start_node,
            '結束節次': end_node,
            '上課地點': l.strip()
        })
    return results

def load_teacher_set(dict_path):
    """載入教師字典"""
    dict_path = Path(dict_path)
    if not dict_path.exists():
        print(f"[Warning] 找不到字典檔：{dict_path}，將無法正確拆分黏連姓名。")
        return set(), 4
    
    try:
        df = pd.read_csv(dict_path, encoding='utf-8-sig')
        t_set = set(df['teacher_name'].dropna().astype(str))
        max_name_len = max([len(n) for n in t_set]) if t_set else 4
        return t_set, max_name_len
    except Exception as e:
        print(f"[Error] 讀取字典失敗：{e}")
        return set(), 4

def split_teachers_by_dict(text, teacher_set, max_name_len):
    """正向最大匹配：針對黏在一起的字串進行切分"""
    result = []
    n = len(text)
    i = 0
    loop_limit = n * 2
    count = 0
    
    while i < n:
        matched = None
        window = min(n - i, max_name_len)
        for width in range(window, 1, -1):
            candidate = text[i : i + width]
            if candidate in teacher_set:
                matched = candidate
                break
        
        if matched:
            result.append(matched)
            i += len(matched)
        else:
            i += 1 
        count += 1
        if count > loop_limit: 
            break
            
    return result if result else [text]

def split_teachers(row, teacher_set, max_name_len):
    """教師姓名處理入口"""
    teacher_str = row.get('教師姓名')
    if pd.isna(teacher_str):
        return []

    text = str(teacher_str).strip()
    if text in ['校際教師', '校外教師']:
        return ['校際教']
    return split_teachers_by_dict(text, teacher_set, max_name_len)

def clean_single_file(csv_file, teacher_set, max_name_len):
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
    except (FileNotFoundError, pd.errors.EmptyDataError, UnicodeDecodeError) as e:
        print(f"讀取檔案失敗 {csv_file}: {e}")
        return None

    year, semester = extract_year_semester_from_filename(csv_file)
    if year is None: return None

    df['學年度'] = year
    df['學期'] = semester

    # 1. 課程名稱處理
    df[['中文課程名稱', '英文課程名稱']] = df['課程名稱'].apply(split_course_name)
    
    # 2. 上課節次與地點處理
    df['parsed_schedule'] = df['上課節次+地點'].apply(parse_schedule_location)
    df = df.explode('parsed_schedule')
    df.reset_index(drop=True, inplace=True)
    
    schedule_df = pd.json_normalize(df['parsed_schedule'])
    df = pd.concat([df.drop(columns=['parsed_schedule']), schedule_df], axis=1)
    
    # 3. 教師姓名處理
    df['教師列表'] = df.apply(lambda row: split_teachers(row, teacher_set, max_name_len), axis=1)
    df['教師列表'] = df['教師列表'].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
    
    # 4. 星期格式優化
    if '星期' in df.columns:
        df['星期'] = df['星期'].astype(str).str.replace(r'[()]', '', regex=True).replace('nan', '', regex=False)
        
    # 5. 文字欄位補值
    text_cols_to_fill = ['備註', '英文課程名稱', '教師姓名', '上課地點', '上課大樓', '上課節次+地點']
    for col in text_cols_to_fill:
        if col in df.columns:
            df[col] = df[col].fillna("")

    # 6. 數值欄位補值與轉型
    count_cols = ['上限人數', '登記人數', '選上人數']
    for col in count_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    if '全英語授課' in df.columns:
        df['全英語授課'] = df['全英語授課'].map({'是': True, '否': False}).fillna(False)

    cols_to_keep = [
        '學年度', '學期', '序號', '課程代碼', '開課班別(代表)',
        '教學大綱Syllabus', '教學大綱連結',
        '課程名稱', '中文課程名稱', '英文課程名稱',
        '課程性質', '課程性質2', '全英語授課', '學分',
        '教師姓名', '教師列表',
        '上課大樓', '上課節次+地點',
        '星期', '起始節次', '結束節次', '上課地點',
        '上限人數', '登記人數', '選上人數',
        '可跨班', '備註'
    ]
    final_cols = [c for c in cols_to_keep if c in df.columns]
    return df[final_cols]

def build_all_courses_dataset(input_dir, teacher_dict_path):
    input_dir = Path(input_dir)
    csv_files = sorted(input_dir.glob("courses_*.csv"))

    if not csv_files:
        raise RuntimeError(f"{input_dir} 內找不到 courses_*.csv")

    print(f"正在載入教師字典：{teacher_dict_path}")
    teacher_set, max_name_len = load_teacher_set(teacher_dict_path)
    print(f"字典載入完成，共 {len(teacher_set)} 位教師，最長姓名長度：{max_name_len}")

    dfs = []
    for csv_file in csv_files:
        print(f"處理中：{csv_file.name}")
        df_clean = clean_single_file(csv_file, teacher_set, max_name_len)
        if df_clean is not None:
            dfs.append(df_clean)

    if not dfs:
        return pd.DataFrame()

    all_df = pd.concat(dfs, ignore_index=True)
    print(f"合併完成，共 {len(all_df)} 筆資料")
    return all_df

if __name__ == "__main__":
    BASE_DIR = Path(".") 
    INPUT_DIR = BASE_DIR / "raw_data"
    DICT_PATH = BASE_DIR / "dict" / "teacher.csv"
    OUTPUT_DIR = BASE_DIR / "processed_data"
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        final_df = build_all_courses_dataset(INPUT_DIR, DICT_PATH)
        if not final_df.empty:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_DIR / f"all_courses_{timestamp}.csv"
            final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"\n成功！最終檔案已儲存：{output_path}")
    except Exception as e:
        print(f"\n發生錯誤：{e}")
        import traceback
        traceback.print_exc()