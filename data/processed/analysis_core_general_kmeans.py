import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ===============================
# 1. 讀取資料
# ===============================
FILE_PATH = "all_courses_20260106_132323.csv"
df = pd.read_csv(FILE_PATH, low_memory=False)

print("原始資料筆數：", len(df))
print("欄位列表：")
print(df.columns.tolist())

# ===============================
# 2. 制度分類：核心通識（用科系判斷）
# ===============================
# ⚠️ 請確認你的資料中「通識教育中心」實際名稱
TARGET_DEPT_KEYWORD = "通識"

df_core = df[df["科系"].astype(str).str.contains(TARGET_DEPT_KEYWORD, na=False)].copy()

print("核心通識課程筆數：", len(df_core))

# ===============================
# 3. 建立行為型特徵
# ===============================
# 避免除以 0
df_core = df_core[
    (df_core["登記人數"] > 0) &
    (df_core["上限人數"] > 0)
].copy()

# 中籤率（選上人數 / 登記人數）
df_core["中籤率"] = df_core["選上人數"] / df_core["登記人數"]

# 飽和度（選上人數 / 上限人數）
df_core["飽和度"] = df_core["選上人數"] / df_core["上限人數"]

print("清洗後可分析課程數：", len(df_core))

# ===============================
# 4. 分群用特徵
# ===============================
features = df_core[["中籤率", "飽和度"]].copy()

# ===============================
# 5. 特徵標準化
# ===============================
scaler = StandardScaler()
X_scaled = scaler.fit_transform(features)

# ===============================
# 6. K-means 分群
# ===============================
K = 4
kmeans = KMeans(n_clusters=K, random_state=42, n_init=10)
df_core["cluster"] = kmeans.fit_predict(X_scaled)

# ===============================
# 7. 分群統計（報告用）
# ===============================
summary = df_core.groupby("cluster")[["中籤率", "飽和度"]].mean()
count = df_core["cluster"].value_counts().sort_index()

print("\n=== 各群平均行為特徵 ===")
print(summary)

print("\n=== 各群課程數量 ===")
print(count)

# ===============================
# 8. 視覺化
# ===============================
plt.figure(figsize=(10, 7))

scatter = plt.scatter(
    df_core["飽和度"],
    df_core["中籤率"],
    c=df_core["cluster"],
    cmap="tab10",
    alpha=0.7
)

plt.xlabel("飽和度（選上人數 / 上限人數）")
plt.ylabel("中籤率（選上人數 / 登記人數）")
plt.title("核心通識課程之選課行為分群（K-means）")

plt.colorbar(scatter, label="Cluster")
plt.grid(True)
plt.tight_layout()
plt.show()

# ===============================
# 9. 輸出結果
# ===============================
OUTPUT_FILE = "core_general_kmeans_result.csv"
df_core.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"\n分析完成，結果已輸出：{OUTPUT_FILE}")