import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import seaborn as sns
import matplotlib.pyplot as plt

# 設定中文字型 (避免圖表亂碼)，若在 Colab 可略過或改用其他字型
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
plt.rcParams['axes.unicode_minus'] = False

def run_clustering(input_file='cleaned_courses.csv', output_file='clustered_courses4.csv'):
    print("開始執行 K-Means 分群分析...")

    # 1. 讀取清洗後的資料
    df = pd.read_csv(input_file)
    print(f"讀取資料筆數: {len(df)}")

    # 2. 選擇關鍵特徵 (Features)
    # 這些欄位決定了分群的依據
    features = ['學分', '上限人數', '飽和度', '中籤率', '全英_數值', '起始節次']
    
    # 檢查是否有缺失值，若有則補 0 或平均值
    X = df[features].fillna(0)

    # 3. 資料標準化 (Standardization)
    # 重要！因為人數是幾十，飽和度是小數，必須縮放到同一尺度
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 4. 訓練 K-Means 模型
    # 設定分群數量 K=5 (可根據手肘法調整，但 5 通常夠用)
    k = 5
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    
    # 預測每堂課屬於哪一群
    df['Cluster'] = kmeans.fit_predict(X_scaled)
    
    print(f"分群完成！將課程分為 {k} 類")

    # 5. 分析分群結果 (Cluster Profiling)
    # 計算每一群的平均特徵，讓我們知道這一群是什麼樣的課
    summary = df.groupby('Cluster')[features].mean()
    summary['課程數量'] = df['Cluster'].value_counts()
    
    # 重新命名欄位以便閱讀
    summary.columns = ['平均學分', '平均上限人數', '平均飽和度', '平均中籤率', '全英比例', '平均開始節次', '課程數量']
    
    print("\n分群結果摘要表：")
    print(summary)

    # 6. 為每一群貼上人類可讀的標籤 (Tagging)
    # 根據 summary 的結果自動貼標籤 (這裡的邏輯是根據你的資料特性寫死的，可依實際結果調整)
    def label_cluster(row):
        cluster_id = row['Cluster']
        if cluster_id == 0:
            return "全英授課"
        elif cluster_id == 1:
            return "冷門課程"
        elif cluster_id == 2:
            return "搶手熱門"
        elif cluster_id == 3:
            return "小班/研究所"
        else:
            return "一般課程"

    df['標籤'] = df.apply(label_cluster, axis=1)

    # 7. 儲存結果
    # 只保留重要欄位存檔，減少檔案大小
    output_cols = ['學年度', '學期', '課程代碼', '中文課名', '英文課名', '系所', '學分', '授課教師', '星期', '起始節次', '結束節次', '地點', '飽和度', '中籤率', 'Cluster', '標籤']
    # 如果要把所有欄位都存，就直接存 df
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"結果已儲存至: {output_file}")

    # (選用) 視覺化：繪製熱門度 vs 中籤率 的散佈圖
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='飽和度', y='中籤率', hue='Cluster', palette='viridis', alpha=0.6)
    plt.title('課程分群視覺化：熱門度 vs 難搶程度')
    plt.xlabel('飽和度 (登記/上限)')
    plt.ylabel('中籤率 (選上/登記)')
    plt.axvline(x=1.0, color='r', linestyle='--', alpha=0.3) # 飽和線
    plt.savefig('cluster_plot4.png')
    print("分群視覺化圖表已儲存為 cluster_plot4.png")

if __name__ == "__main__":
    run_clustering()