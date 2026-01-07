import pandas as pd
import numpy as np
import os

def classify_final(input_file='result/course_cleaned2.csv', output_file='course_cluster3.csv'):
    print("🚀 開始執行最終分類架構 (NCUE Framework)...")
    
    # 1. 讀取資料
    # 檢查檔案是否存在，支援多種路徑
    possible_paths = [input_file, 'data/' + input_file, 'result/' + input_file]
    df = None
    for path in possible_paths:
        if os.path.exists(path):
            print(f"📦 讀取檔案: {path}")
            df = pd.read_csv(path)
            break
            
    if df is None:
        print(f"❌ 找不到輸入檔案: {input_file}")
        return

    # ==========================================
    # STEP 1: 定義第一層分類 (Category)
    # ==========================================
    print("🏷️ 正在進行科系分類 (依據畢業門檻)...")
    
    def get_category(row):
        # 轉成字串避免錯誤
        dept = str(row.get('科系', ''))
        cls = str(row.get('開課班別(代表)', ''))
        name = str(row.get('課程名稱', ''))
        college = str(row.get('學院', ''))

        # 1. 精進中文 (畢業門檻)
        if '精進中文' in dept or '精進中文' in cls or '國文' in dept:
            # 排除國文系的專業課 (如果開課班別是國文系而非通識中心)
            # 但通常精進中文會標記清楚，這裡以關鍵字優先
            if '精進' in cls or '精進' in dept:
                return '精進中文'

        # 2. 精進英外文 (畢業門檻)
        if '精進英外文' in cls or '英文精進' in dept:
            return '精進英外文'
        
        # 3. 核心通識 (畢業門檻)
        if '通識' in dept or '通識' in cls or '博雅' in cls:
            return '核心通識'
            
        # 4. 師培課程 (額外學程)
        if '教育學程' in cls or '師資' in dept:
            return '師培課程'

        # 5. 體育/軍訓 (校必修)
        # 雖然你主要分5類，但體育是必修，建議獨立或歸類
        if '體育' in dept or '軍訓' in dept:
            # 排除體育系的專業課
            if '運動學系' not in dept and '體育學系' not in dept:
                return '體育/軍訓'

        # 6. 專業科系課程 (預設)
        return '專業課程'

    df['分類'] = df.apply(get_category, axis=1)

    # ==========================================
    # STEP 2: 定義學制 (Level)
    # ==========================================
    print("🎓 正在區分學士班與碩博士班...")
    
    def get_level(row):
        cat = row['分類']
        cls = str(row.get('開課班別(代表)', ''))
        
        # 只有專業課程需要細分，其他通常是大學部
        if cat != '專業課程':
            return '大學部'
            
        # 判斷碩博士關鍵字
        grad_keywords = ['碩', '博', '在職', 'MBA', 'IMBA', '專班']
        if any(kw in cls for kw in grad_keywords):
            return '碩博士班'
            
        return '學士班'

    df['學制'] = df.apply(get_level, axis=1)

    # ==========================================
    # STEP 3: 智慧標籤對應 (Cluster Mapping)
    # ==========================================
    print("🤖 正在套用 Cluster 標籤...")
    
    def get_smart_tag(row):
        cluster = row['Cluster']
        cat = row['分類']
        
        # 基礎標籤對照 (根據之前的 K-Means 結果)
        # Cluster 0: 熱門 (High Saturation)
        # Cluster 1: 特殊/論文 (Time=0)
        # Cluster 2: 一般選修 (Afternoon)
        # Cluster 3: 全英 (EMI)
        # Cluster 4: 必修/灌檔 (Manual)

        tag = "一般"
        
        # 針對不同分類，給予不同的解讀文案
        if cat == '核心通識':
            if cluster == 0: tag = "搶手熱門"
            elif cluster == 2: tag = "一般通識" # 好選
            elif cluster == 3: tag = "全英通識"
            elif cluster == 4: tag = "熱門加簽"
            else: tag = "一般通識"
            
        elif cat == '專業課程':
            if cluster == 4: tag = "系上必修" # 通常灌檔的是必修
            elif cluster == 0: tag = "熱門課程"
            elif cluster == 3: tag = "全英專業"
            elif cluster == 1: tag = "專題/論文"
            elif cluster == 2: tag = "一般課程"
            
        elif cat == '師培課程':
            if cluster == 0: tag = "熱門師培"
            else: tag = "師培課程"
            
        elif cat == '精進英外文':
             if cluster == 0: tag = "熱門時段"
             else: tag = "必修英文"
             
        else:
            # 體育或其他
            if cluster == 0: tag = "熱門時段"
            else: tag = "一般課程"
            
        return tag

    df['cluster標籤'] = df.apply(get_smart_tag, axis=1)

    # ==========================================
    # STEP 4: 最終整理與存檔
    # ==========================================
    
    # 重新排列欄位，把重要的放前面
    target_cols = [
        '學年度', '學期', 
        '分類', '學制', 'cluster標籤', # 新增的分析欄位
        '課程名稱', '英文課程名稱', '開課班別(代表)', '科系', '學院', '學分',
        '教師姓名', '星期', '起始節次', '地點',
        '飽和度', '中籤率', '全英', 'Cluster', '教學大綱連結'
    ]
    
    # 只保留存在的欄位
    final_cols = [c for c in target_cols if c in df.columns]
    df_final = df[final_cols]
    
    # 存檔
    df_final.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"✅ 處理完成！結果已儲存至: {output_file}")
    
    # 印出統計摘要，讓使用者確認
    print("\n📊 課程分類統計摘要:")
    summary = df_final.groupby(['分類', '學制']).size().reset_index(name='課程數量')
    print(summary)
    
    print("\n📊 核心通識的標籤分佈:")
    ge_summary = df_final[df_final['分類'] == '核心通識']['cluster標籤'].value_counts()
    print(ge_summary)

if __name__ == "__main__":
    classify_final()