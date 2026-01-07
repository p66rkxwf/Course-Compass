import pandas as pd
import re
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

def clean_and_analyze(input_file='data/all_courses_20260102_023143.csv', output_file='result/course_cleaned1.csv'):
    print("🚀 開始執行 V5：資料深度清洗、特徵工程與分群分析...")
    
    # 1. 讀取資料
    try:
        df = pd.read_csv(input_file)
        print(f"📦 成功讀取 {len(df)} 筆資料。")
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {input_file}")
        return

    # ==========================================
    # PART 1: 時間與地點深度解析 (Time Parsing)
    # ==========================================
    print("⏳ 正在重新解析時間與地點 (填補缺失值)...")
    week_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '日': 7}
    
    def parse_time(raw):
        if pd.isna(raw): return None, None, None, None
        raw = str(raw)
        
        # 提取星期 (Day)
        day_match = re.search(r'\((\w+)\)', raw)
        day = week_map.get(day_match.group(1), 0) if day_match else 0
        
        # 清除星期部分，剩下時間與地點
        rest = re.sub(r'\(.*?\)', '', raw).strip()
        parts = rest.split()
        
        s, e = 0, 0
        loc = "Unknown"
        
        if parts:
            time_part = parts[0]
            # 判斷第一部分是否包含數字 (是時間還是地點?)
            if re.search(r'\d', time_part):
                if '-' in time_part:
                    try:
                        # 處理 "01-02" 或 "01-02,05" 等格式
                        clean_time = re.sub(r'[^\d\-]', '', time_part.split(',')[0]) 
                        s, e = [float(x) for x in clean_time.split('-')[:2]]
                    except: pass
                elif time_part.isdigit():
                    s = e = float(time_part)
                
                # 如果第一部分是時間，那第二部分之後通常是地點
                if len(parts) > 1:
                    loc = " ".join(parts[1:])
            else:
                # 第一部分不是時間，那整串可能都是地點
                loc = " ".join(parts)
        
        return day, s, e, loc

    # 應用解析函數
    t_data = df['上課節次+地點'].apply(parse_time)
    
    df['星期'] = [x[0] for x in t_data]
    df['起始節次'] = [x[1] for x in t_data]
    df['結束節次'] = [x[2] for x in t_data]
    df['地點'] = [x[3] for x in t_data]
    
    # 填補缺失值 (預設為 0)
    df['星期'] = df['星期'].fillna(0)
    df['起始節次'] = df['起始節次'].fillna(0)
    df['結束節次'] = df['結束節次'].fillna(0)

    # ==========================================
    # PART 2: 英文課名補全 (Name Cleaning)
    # ==========================================
    print("🔤 檢查並補全缺失的英文課程名稱...")
    
    def fill_english_name(row):
        # 如果原本就有英文課名，直接用
        existing_en = str(row['英文課程名稱']) if pd.notna(row['英文課程名稱']) else ""
        if existing_en.strip() != "":
            return existing_en
            
        # 如果缺失，使用 V4 邏輯從中文名稱提取
        raw = str(row['課程名稱']).strip()
        # 如果沒中文，整串視為英文
        if not re.search(r'[\u4e00-\u9fff]', raw):
            return raw 
            
        # 找最後一個中文字
        zh_matches = list(re.finditer(r'[\u4e00-\u9fff]', raw))
        if not zh_matches: return ""
        
        last_zh_idx = zh_matches[-1].end()
        tail = raw[last_zh_idx:]
        
        # 找英文開頭
        en_match = re.search(r'[a-zA-Z]', tail)
        
        if en_match:
            split_idx = last_zh_idx + en_match.start()
            # 處理括號歸屬
            if split_idx - 1 >= 0 and raw[split_idx-1] in ['(', '（']:
                split_idx -= 1
            return raw[split_idx:].strip()
        return ""

    df['英文課程名稱'] = df.apply(fill_english_name, axis=1)

    # ==========================================
    # PART 3: 特徵工程 (Feature Engineering)
    # ==========================================
    print("🧮 計算分析指標 (飽和度、中籤率)...")
    
    # 1. 飽和度 (登記/上限)
    df['飽和度'] = df['登記人數'] / df['上限人數'].replace(0, 1)
    
    # 2. 中籤率 (選上/登記)
    # 若無人登記，設為 1.0 (容易選上)
    df['中籤率'] = df.apply(lambda x: x['選上人數'] / x['登記人數'] if x['登記人數'] > 0 else 1.0, axis=1)
    
    # 3. 全英授課數值化
    df['全英'] = df['全英語授課'].apply(lambda x: 1 if str(x).lower() == 'true' or x is True else 0)
    
    # 4. 熱門標籤 (用於關聯分析)
    df['Is_Hot'] = df['飽和度'] >= 1.0

    # ==========================================
    # PART 4: K-Means 分群 (Clustering)
    # ==========================================
    print("🤖 執行 K-Means 分群 (K=5)...")
    
    features = ['學分', '上限人數', '飽和度', '中籤率', '全英', '起始節次', '結束節次', '星期']
    X = df[features].fillna(0)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    # 產出整數 Cluster ID (0-4)
    df['Cluster'] = kmeans.fit_predict(X_scaled)
    
    # 印出分群中心點供參考
    print("\n--- 分群結果解讀 (Cluster Interpretation) ---")
    print(df.groupby('Cluster')[features].mean())

    # ==========================================
    # PART 5: 關聯性法則分析 (Association Analysis)
    # ==========================================
    print("\n🔍 關聯性分析摘要 (Association Insights):")
    
    # 1. 哪個學院最熱門?
    if '學院' in df.columns:
        print("\n[各學院熱門課程比例 Top 5]")
        print(df.groupby('學院')['Is_Hot'].mean().sort_values(ascending=False).head(5))
        
    # 2. 星期幾最難搶?
    print("\n[星期幾最熱門 (1=週一, 5=週五)]")
    print(df.groupby('星期')['Is_Hot'].mean().sort_values(ascending=False).head(5))

    # ==========================================
    # PART 6: 存檔
    # ==========================================
    output_cols = [
        '學年度', '學期', '課程代碼', '課程名稱', '英文課程名稱', '開課班別(代表)', '學院', '科系',
        '學分', '教師姓名', '星期', '起始節次', '結束節次', '地點',
        '上限人數', '登記人數', '選上人數', '飽和度', '中籤率', '全英', 'Cluster', '教學大綱連結'
    ]
    
    # 只保留存在的欄位
    final_cols = [c for c in output_cols if c in df.columns]
    
    df[final_cols].to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"✅ 處理完成！結果已儲存至 {output_file}")

if __name__ == "__main__":
    clean_and_analyze()