import pandas as pd
import re
import numpy as np

def clean_data(input_file='all_courses_20251227_160504.csv', output_file='cleaned_courses.csv'):
    print("開始執行資料前處理 (Data Preprocessing)...")
    
    # 1. 讀取資料
    df = pd.read_csv(input_file)
    print(f"原始資料筆數：{len(df)}")

    # ==========================================
    # PART 1: 時間欄位深度清洗 (Time Parsing)
    # ==========================================
    print("正在清洗時間與節次...")

    # 定義星期映射表
    week_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '日': 7}

    def parse_time_location(raw_str):
        """
        解析字串: "(三) 05-07 LC202" -> (3, 5, 7, 'LC202')
        解析字串: "(二) 08-09、14" -> (2, 8, 9, 'Unknown') # 取第一段時間
        """
        if pd.isna(raw_str) or str(raw_str).strip() == "":
            return None, None, None, None
        
        raw_str = str(raw_str).strip()
        
        # 1. 提取星期: 抓取括號內的字
        day_match = re.search(r'\((\w+)\)', raw_str)
        day_num = None
        if day_match:
            day_char = day_match.group(1)
            day_num = week_map.get(day_char, None)
        
        # 2. 提取節次: 抓取括號後的數字部分 (支援 05-07 或 05,06 或 05)
        # 先去掉星期部分
        rest_str = re.sub(r'\(.*?\)', '', raw_str).strip()
        
        start_period = None
        end_period = None
        location = None
        
        # 嘗試切分 "時間" 和 "地點" (通常中間有空格)
        parts = rest_str.split()
        time_part = parts[0] if parts else ""
        location = parts[1] if len(parts) > 1 else "Unknown"
        
        # 解析時間段 (例如 05-07)
        if '-' in time_part:
            try:
                s, e = time_part.split('-')
                start_period = float(re.sub(r'\D', '', s)) # 只留數字
                end_period = float(re.sub(r'\D', '', e.split('、')[0])) # 處理像 09、14
            except:
                pass
        elif time_part.isdigit():
            start_period = float(time_part)
            end_period = float(time_part)
            
        return day_num, start_period, end_period, location

    # 應用解析函數
    parsed_data = df['上課節次+地點'].apply(parse_time_location)
    
    # 將結果拆分到新欄位
    df['星期'] = [x[0] for x in parsed_data]
    df['起始節次'] = [x[1] for x in parsed_data]
    df['結束節次'] = [x[2] for x in parsed_data]
    df['地點'] = [x[3] for x in parsed_data]

    # 填補空值：若原始欄位有值但解析失敗，用既有欄位或中位數補
    df['星期'] = df['星期'].fillna(df['星期'].map(week_map))
    # 若還是空，設為 0 (無時間)
    df['星期'] = df['星期'].fillna(0)
    df['起始節次'] = df['起始節次'].fillna(df['起始節次']).fillna(0)
    df['結束節次'] = df['結束節次'].fillna(df['結束節次']).fillna(0)

    # ==========================================
    # PART 2: 系所與學院對照 (Mapping)
    # ==========================================
    print("正在建立學院與系所標籤...")
    
    # 根據你的 ID Mapping 規則
    dept_map = {
        '11': '輔諮系', '12': '特教系', '13': '教研所', '14': '復健所',
        '21': '科教所', '22': '數學系', '23': '物理系', '24': '生物系', '25': '化學系', '26': '光電所',
        '31': '工教系', '32': '人資所',
        '41': '英文系', '42': '國文系', '43': '地理系', '44': '美術系', '48': '台文所',
        '51': '機電系', '52': '電機系', '53': '電子系', '54': '資工系',
        '61': '資管系', '62': '會計系', '63': '企管系', '67': '財金系',
        '71': '運動系', '78': '公育系'
    }
    college_map = {
        '1': '教育學院', '2': '理學院', '3': '科技學院',
        '4': '文學院', '5': '工學院', '6': '管理學院', '7': '社科體育學院'
    }

    def map_id(code):
        code = str(code)
        if len(code) < 2: return '其他', '其他'
        d_code = code[:2]
        c_code = code[:1]
        dept = dept_map.get(d_code, '其他/通識')
        college = college_map.get(c_code, '其他/通識')
        return dept, college

    df[['系所', '學院']] = df['課程代碼'].apply(lambda x: pd.Series(map_id(x)))

    # ==========================================
    # PART 3: 數值特徵計算 (Feature Engineering)
    # ==========================================
    print("正在計算熱門度指標...")

    # 飽和度 (登記/上限)
    df['飽和度'] = df['登記人數'] / df['上限人數'].replace(0, 1) # 避免除以0
    
    # 中籤率 (選上/登記)
    # 若無人登記(0)，設為 1.0 (代表必上)
    df['中籤率'] = df.apply(lambda x: x['選上人數'] / x['登記人數'] if x['登記人數'] > 0 else 1.0, axis=1)

    # 全英授課轉數值
    df['全英_數值'] = df['全英語授課'].apply(lambda x: 1 if x == True or x == 'True' else 0)

    # ==========================================
    # PART 4: 最終整理與存檔
    # ==========================================
    # 選取分析所需的乾淨欄位
    output_columns = [
        '學年度', '學期', '課程代碼', '課程名稱', '系所', '學院', '開課班別(代表)',
        '學分', '全英_數值', '授課教師', '星期', '起始節次', '結束節次', '地點',
        '上限人數', '登記人數', '選上人數', '飽和度', '中籤率', '備註', '教學大綱連結'
    ]
    
    # 重新命名欄位以便閱讀
    df.rename(columns={'教師姓名': '授課教師'}, inplace=True)
    
    # 確保只輸出存在的欄位
    final_cols = [c for c in output_columns if c in df.columns]
    df_clean = df[final_cols]
    
    df_clean.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"資料前處理完成！已儲存至: {output_file}")
    print(f"範例資料:\n{df_clean[['課程名稱', '星期', '起始節次', '飽和度']].head()}")

if __name__ == "__main__":
    clean_data()