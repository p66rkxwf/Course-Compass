import pandas as pd
import re
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

def clean_and_cluster(input_file='all_courses_20251227_160504.csv', output_file='final_courses_v4.csv'):
    print("開始執行 V4：修正括號歸屬 + 完整保留純英文課名...")
    
    # 1. 讀取資料
    try:
        df = pd.read_csv(input_file)
        print(f"原始資料筆數: {len(df)}")
    except FileNotFoundError:
        print(f"找不到檔案: {input_file}，請確認檔案名稱與路徑。")
        return

    # ==========================================
    # PART 1: V4 強力課名切割演算法
    # ==========================================
    print("正在執行中英文課名分離 (V4 Logic)...")

    def split_name_v4(row):
        # 優先使用既有欄位
        if '中文課程名稱' in row and pd.notna(row['中文課程名稱']):
            return row['中文課程名稱'], row.get('英文課程名稱', "")
            
        raw = str(row['課程名稱']).strip()
        
        # 情況 A: 純英文課程 (或無中文)
        # 檢查是否包含中文字 (\u4e00-\u9fff)
        if not re.search(r'[\u4e00-\u9fff]', raw):
            # 如果沒有中文，則 "中文名" 和 "英文名" 都設為原名，確保資料完整
            # 這樣 "English & English" 就會完整保留
            return raw, raw
            
        # 情況 B: 混合名稱，需切割
        # 1. 找出「最後一個中文字」的位置
        zh_matches = list(re.finditer(r'[\u4e00-\u9fff]', raw))
        last_zh_idx = zh_matches[-1].end() # 最後一個中文字的"後面"那個位置
        
        # 取得剩餘的字串 (Tail)
        tail = raw[last_zh_idx:]
        
        # 2. 在剩餘字串中，尋找「第一個英文字母」
        en_match = re.search(r'[a-zA-Z]', tail)
        
        if not en_match:
            # 如果後面沒有英文字母 (例如: "體育(一)")
            return raw, ""
            
        # 找到英文在 tail 中的起始位置
        en_start_in_tail = en_match.start()
        # 換算成絕對位置
        split_idx = last_zh_idx + en_start_in_tail
        
        # 3. [關鍵修正] 括號歸屬判斷
        # 檢查英文字母的前一個字元，如果是 '('，要把它算進英文名裡
        # 但如果是 ')' (如 體育(一)Physical)，則不需要動
        
        # 往回看一個字元
        check_idx = split_idx - 1
        if check_idx >= last_zh_idx:
            char_before = raw[check_idx]
            if char_before in ['(', '（']:
                # 修正：將切割點前移，包含括號
                split_idx = check_idx
            # 你也可以在這裡處理 " - " 等符號，目前先針對括號處理
            
        zh_part = raw[:split_idx].strip()
        en_part = raw[split_idx:].strip()
        
        # 清理中文名後面多餘的符號 (如 "中文名稱 -")
        zh_part = zh_part.strip(" -:：")
        
        return zh_part, en_part

    names = df.apply(split_name_v4, axis=1)
    df['中文課名'] = [x[0] for x in names]
    df['英文課名'] = [x[1] for x in names]

    # ==========================================
    # PART 2: 時間與系所清洗 (維持原樣)
    # ==========================================
    print("清洗時間與系所...")
    week_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '日': 7}
    
    def parse_time(raw):
        if pd.isna(raw): return None, None, None, None
        raw = str(raw)
        day_match = re.search(r'\((\w+)\)', raw)
        day = week_map.get(day_match.group(1), 0) if day_match else 0
        rest = re.sub(r'\(.*?\)', '', raw).strip()
        parts = rest.split()
        loc = parts[1] if len(parts) > 1 else "Unknown"
        s, e = 0, 0
        if parts:
            time_str = parts[0]
            if '-' in time_str:
                try:
                    s, e = [float(re.sub(r'\D', '', x)) for x in time_str.split('-')[:2]]
                except: pass
            elif time_str.isdigit():
                s = e = float(time_str)
        return day, s, e, loc

    t_data = df['上課節次+地點'].apply(parse_time)
    df['星期_數值'] = [x[0] for x in t_data]
    df['起始節次'] = [x[1] for x in t_data]
    df['結束節次'] = [x[2] for x in t_data]
    df['地點'] = [x[3] for x in t_data]

    # 系所對照
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
    # PART 3: K-Means 分群與智慧貼標
    # ==========================================
    print("執行 K-Means 分群與智慧貼標...")

    df['飽和度'] = df['登記人數'] / df['上限人數'].replace(0, 1)
    df['中籤率'] = df.apply(lambda x: x['選上人數'] / x['登記人數'] if x['登記人數'] > 0 else 1.0, axis=1)
    df['全英_數值'] = df['全英語授課'].apply(lambda x: 1 if str(x).strip() == 'True' or x is True else 0)
    
    features = ['學分', '上限人數', '飽和度', '中籤率', '全英_數值', '起始節次']
    X = df[features].fillna(0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    df['Cluster'] = kmeans.fit_predict(X_scaled)
    
    cluster_stats = df.groupby('Cluster')[features].mean()
    cluster_labels = {}
    
    emi_cluster = cluster_stats['全英_數值'].idxmax()
    cluster_labels[emi_cluster] = "全英授課"
    
    remaining = cluster_stats.drop(index=[emi_cluster], errors='ignore')
    if not remaining.empty:
        manual_cluster = remaining['中籤率'].idxmax()
        if remaining.loc[manual_cluster, '中籤率'] > 1.5:
            cluster_labels[manual_cluster] = "特殊/加簽"
        else:
            manual_cluster = None
            
    labeled = list(cluster_labels.keys())
    remaining = cluster_stats.drop(index=labeled, errors='ignore')
    if not remaining.empty:
        hot_cluster = remaining['飽和度'].idxmax()
        cluster_labels[hot_cluster] = "搶手熱門"
        
    labeled = list(cluster_labels.keys())
    remaining = cluster_stats.drop(index=labeled, errors='ignore')
    if not remaining.empty:
        small_cluster = remaining['上限人數'].idxmin()
        cluster_labels[small_cluster] = "小班/研究所"
        
    for i in range(5):
        if i not in cluster_labels:
            cluster_labels[i] = "一般課程"

    df['標籤'] = df['Cluster'].map(cluster_labels)

    # ==========================================
    # PART 4: 存檔
    # ==========================================
    output_cols = [
        '學年度', '學期', '課程代碼', '中文課名', '英文課名', '開課班別(代表)',
        '學分', '授課教師', '系所', '學院', '星期_數值', '起始節次', '地點',
        '上限人數', '登記人數', '中籤率', '飽和度', '備註', 'Cluster', '標籤', '教學大綱連結'
    ]
    
    if '教師姓名' in df.columns: df.rename(columns={'教師姓名': '授課教師'}, inplace=True)
    
    final_cols = [c for c in output_cols if c in df.columns]
    
    df[final_cols].to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"V4 完成！結果已儲存至 {output_file}")
    print("\n[V4 更新重點]:")
    print("1. 純英文課名已完整保留 (不再被截斷)")
    print("2. 括號 (English) 已正確歸類至英文名")

if __name__ == "__main__":
    clean_and_cluster()