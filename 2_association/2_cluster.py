import pandas as pd
import numpy as np

def run_classification(input_file='./result/course_cleaned2.csv', output_file='course_cluster2.csv'):
    print("🚀 開始執行階層式分類 (Hierarchy Classification)...")
    
    # 1. 讀取資料
    try:
        df = pd.read_csv(input_file)
        print(f"📦 讀取 {len(df)} 筆課程資料。")
    except FileNotFoundError:
        print("❌ 找不到檔案，請確認檔名。")
        return

    # ==========================================
    # STEP 1: 定義第一層分類 (Category)
    # ==========================================
    print("🏷️ 正在進行第一層分類 (依據科系/學院)...")
    
    def define_category(row):
        dept = str(row['科系'])
        college = str(row['學院'])
        name = str(row['課程名稱'])
        
        # 1. 通識 (General Education)
        if '通識' in dept or '通識' in college:
            return '通識'
            
        # 2. 體育 (Physical Education)
        # 注意：有些體育課可能是系上選修，這裡主要抓全校性體育
        if '體育' in dept or '體育' in name:
            # 排除掉 "體育學系" 的專業課 (通常學院是社科體育學院)
            if '體育學系' not in dept and '運動學系' not in dept:
                return '體育'
            
        # 3. 語文 (Language Center)
        if '語文' in dept or '語文' in college:
            return '語文'
            
        # 4. 教育/師培 (Teacher Ed)
        if '師資' in dept or '教育學程' in dept:
            return '師培'
            
        # 5. 其他都歸類為 "系所專業"
        return '系所'

    df['課程大類'] = df.apply(define_category, axis=1)

    # ==========================================
    # STEP 2: 結合 Cluster 產生描述性文案
    # ==========================================
    print("📝 正在生成描述性文案...")

    # 定義 Cluster 的意義 (根據你之前的分析)
    # Cluster 0: 熱門/通識 (高飽和)
    # Cluster 1: 論文/專題 (特殊)
    # Cluster 2: 一般選修 (下午)
    # Cluster 3: 全英 (EMI)
    # Cluster 4: 必修/灌檔 (高權重)
    
    def create_description(row):
        cat = row['課程大類']
        cluster = row['Cluster']
        
        if cat == '通識':
            if cluster == 0: return "🔥 熱門通識 (需志願序)"
            if cluster == 2: return "✅ 一般通識 (好選)"
            if cluster == 4: return "🔒 保障名額/特殊通識"
            
        elif cat == '系所':
            if cluster == 4: return "🔒 系上必修 (預代)"
            if cluster == 0: return "🔥 熱門選修"
            if cluster == 2: return "📝 一般選修"
            
        elif cat == '體育':
            if cluster == 0: return "🔥 熱門體育"
            
        if cluster == 3: return "🇬🇧 全英課程"
        if cluster == 1: return "🎓 專題/論文"
        
        return "一般課程"

    df['標籤描述'] = df.apply(create_description, axis=1)

    # ==========================================
    # STEP 3: 存檔
    # ==========================================
    output_cols = [
        '學年度', '學期', '課程大類', '標籤描述', # 新增的欄位放前面
        '課程名稱', '科系', '學院', '學分', '教師姓名', 
        '星期', '起始節次', '地點', '飽和度', '中籤率', '全英', 'Cluster', '教學大綱連結'
    ]
    
    # 確保欄位存在
    final_cols = [c for c in output_cols if c in df.columns]
    
    df[final_cols].to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"✅ 分類完成！結果已儲存至: {output_file}")
    
    # 印出統計
    print("\n[分類統計]")
    print(df['課程大類'].value_counts())

if __name__ == "__main__":
    run_classification()