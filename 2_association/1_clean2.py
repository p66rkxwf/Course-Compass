import pandas as pd
import re
import numpy as np
import os
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

def clean_and_analyze(input_file='all_courses_20260102_023143.csv', output_dir='result'):
    print("🚀 開始執行 V6：資料清洗、異常修正與結果存檔...")
    
    # 確保輸出資料夾存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. 讀取資料
    try:
        # 嘗試讀取 (相容使用者可能放在 data/ 或根目錄的情況)
        if not os.path.exists(input_file) and os.path.exists('data/' + input_file):
            input_file = 'data/' + input_file
            
        df = pd.read_csv(input_file)
        print(f"📦 成功讀取 {len(df)} 筆資料。")
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {input_file}，請確認檔案位置。")
        return

    # ==========================================
    # PART 1: 時間與地點深度解析 (含異常修復)
    # ==========================================
    print("⏳ 正在解析時間與地點 (含異常值過濾)...")
    week_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '日': 7}
    
    def parse_time(raw):
        if pd.isna(raw): return None, None, None, None
        raw = str(raw)
        
        # 提取星期
        day_match = re.search(r'\((\w+)\)', raw)
        day = week_map.get(day_match.group(1), 0) if day_match else 0
        
        # 清除星期部分
        rest = re.sub(r'\(.*?\)', '', raw).strip()
        parts = rest.split()
        
        s, e = 0, 0
        loc = "Unknown"
        
        if parts:
            time_part = parts[0]
            # 判斷第一部分是否包含數字
            if re.search(r'\d', time_part):
                try:
                    if '-' in time_part:
                        # 處理 "01-02"
                        clean_time = re.sub(r'[^\d\-]', '', time_part.split(',')[0]) 
                        s, e = [float(x) for x in clean_time.split('-')[:2]]
                    elif time_part.isdigit():
                        s = e = float(time_part)
                except:
                    pass
                
                # [關鍵修正]：過濾異常時間 (例如 570, 101)
                # 一般課程節次通常在 0~16 之間，超過代表可能是教室代碼
                if s > 16 or e > 16:
                    s, e = 0, 0
                    # 這種情況下，原本的 time_part 其實是地點
                    loc = " ".join(parts)
                else:
                    # 正常時間，則剩下的部分是地點
                    if len(parts) > 1:
                        loc = " ".join(parts[1:])
            else:
                loc = " ".join(parts)
        
        return day, s, e, loc

    t_data = df['上課節次+地點'].apply(parse_time)
    
    df['星期'] = [x[0] for x in t_data]
    df['起始節次'] = [x[1] for x in t_data]
    df['結束節次'] = [x[2] for x in t_data]
    df['地點'] = [x[3] for x in t_data]
    
    # 填補缺失值
    df[['星期', '起始節次', '結束節次']] = df[['星期', '起始節次', '結束節次']].fillna(0)

    # ==========================================
    # PART 2: 英文課名補全
    # ==========================================
    print("🔤 檢查並補全缺失的英文課程名稱...")
    
    def fill_english_name(row):
        existing_en = str(row['英文課程名稱']) if pd.notna(row['英文課程名稱']) else ""
        if existing_en.strip() != "":
            return existing_en
            
        raw = str(row['課程名稱']).strip()
        if not re.search(r'[\u4e00-\u9fff]', raw):
            return raw 
            
        zh_matches = list(re.finditer(r'[\u4e00-\u9fff]', raw))
        if not zh_matches: return ""
        
        last_zh_idx = zh_matches[-1].end()
        tail = raw[last_zh_idx:]
        
        en_match = re.search(r'[a-zA-Z]', tail)
        if en_match:
            split_idx = last_zh_idx + en_match.start()
            if split_idx - 1 >= 0 and raw[split_idx-1] in ['(', '（']:
                split_idx -= 1
            return raw[split_idx:].strip()
        return ""

    df['英文課程名稱'] = df.apply(fill_english_name, axis=1)

    # ==========================================
    # PART 3: 特徵工程
    # ==========================================
    print("🧮 計算分析指標...")
    
    df['飽和度'] = df['登記人數'] / df['上限人數'].replace(0, 1)
    df['中籤率'] = df.apply(lambda x: x['選上人數'] / x['登記人數'] if x['登記人數'] > 0 else 1.0, axis=1)
    df['全英'] = df['全英語授課'].apply(lambda x: 1 if str(x).lower() == 'true' or x is True else 0)
    df['Is_Hot'] = df['飽和度'] >= 1.0

    # ==========================================
    # PART 4: K-Means 分群
    # ==========================================
    print("🤖 執行 K-Means 分群 (K=5)...")
    
    features = ['學分', '上限人數', '飽和度', '中籤率', '全英', '起始節次', '結束節次', '星期']
    X = df[features].fillna(0)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    df['Cluster'] = kmeans.fit_predict(X_scaled)
    
    # 計算分群摘要 (Centroids)
    cluster_summary = df.groupby('Cluster')[features].mean()
    cluster_summary['課程數量'] = df['Cluster'].value_counts()
    
    print("\n--- 分群結果解讀 ---")
    print(cluster_summary)

    # [新增] 儲存分群摘要表
    summary_path = f"{output_dir}/cluster_summary.csv"
    cluster_summary.to_csv(summary_path, encoding='utf-8-sig')
    print(f"💾 分群摘要已儲存至: {summary_path}")

    # ==========================================
    # PART 5: 關聯性法則分析與存檔
    # ==========================================
    print("\n🔍 執行關聯性分析並存檔...")
    
    assoc_results = []
    
    # 1. 學院熱門度
    if '學院' in df.columns:
        college_stats = df.groupby('學院')['Is_Hot'].mean().sort_values(ascending=False)
        college_stats.name = '熱門比例'
        college_df = college_stats.reset_index()
        college_df['分析類型'] = '學院熱門度'
        college_df.rename(columns={'學院': '項目'}, inplace=True)
        assoc_results.append(college_df)
        
    # 2. 星期熱門度
    day_stats = df.groupby('星期')['Is_Hot'].mean().sort_values(ascending=False)
    day_df = day_stats.reset_index()
    day_df['分析類型'] = '星期熱門度'
    day_df.rename(columns={'星期': '項目', 'Is_Hot': '熱門比例'}, inplace=True)
    assoc_results.append(day_df)
    
    # 合併並儲存
    if assoc_results:
        final_assoc = pd.concat(assoc_results, ignore_index=True)
        assoc_path = f"{output_dir}/association_stats.csv"
        final_assoc.to_csv(assoc_path, index=False, encoding='utf-8-sig')
        print(f"💾 關聯分析已儲存至: {assoc_path}")

    # ==========================================
    # PART 6: 儲存主資料表
    # ==========================================
    output_cols = [
        '學年度', '學期', '序號', '課程代碼', '開課班別(代表)', '學院', '科系', '年級', '班級',
        '教學大綱Syllabus', '教學大綱連結', '教學大綱狀態',
        '課程名稱', '英文課程名稱', '課程性質', '課程性質2',
        '全英', '學分', '教師姓名', '教師列表',
        '星期', '起始節次', '結束節次', '上課地點',
        '上限人數', '登記人數', '選上人數', '中籤率', '飽和度', 'Is_Hot', 'Cluster',
        '可跨班', '備註', 
    ]
    
    final_cols = [c for c in output_cols if c in df.columns]
    
    main_output_path = f"{output_dir}/course_cleaned3.csv"
    df[final_cols].to_csv(main_output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 主資料表已儲存至: {main_output_path}")

if __name__ == "__main__":
    clean_and_analyze()