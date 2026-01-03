# 🎓 大學智慧排課與通識推薦系統

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Pandas](https://img.shields.io/badge/Library-Pandas-orange.svg)

本專案開發一套專為大學生設計的**智慧排課推薦演算法**。使用者只需輸入所屬系級並挑選必/選修課程，系統將自動進行「衝堂偵測」，並基於「歷史大數據」推薦最適合的核心通識課程。

## 🌟 核心功能

- **Step 1: 系級課表自動提取** - 自動過濾出當前學期（114-2）該班級的所有必修與選修課。
- **動態衝堂偵測** - 採用區間重疊演算法（Interval Overlap），精準計算每節課的占用時間，確保行程不衝突。
- **大數據排序推薦** - 利用 111-113 學年度的真實資料預測課程熱度：
  - **歷史飽和度 (Popularity)**：預測哪些通識課最熱門、最值得搶先登記。
  - **歷史中籤率 (Luck Rate)**：在熱門課程中，分析哪些課選上的機率較高（CP 值）。

## 🛠️ 技術邏輯

系統運作分為三個階段：

1. **時間建模**：將課程時間轉化為數學區間 $I = [start, start + credit - 1]$。
2. **衝突判斷**：對每一門候選通識課 $G$ 與已選清單 $S$ 進行交集檢查：
   $$Conflict = (G_{day} == S_{day}) \land (\max(G_{start}, S_{start}) \le \min(G_{end}, S_{end}))$$
3. **加權排序**：對無衝突課程執行排序 `sort(History_Saturation DESC, History_Rate DESC)`。



## 📊 資料集說明

請確保根目錄下存有 `course_cluster3(1).csv`，關鍵欄位包含：
- `開課班別(代表)`：用於區分系級與核心通識。
- `星期`、`起始節次`、`學分`：排課邏輯核心。
- `飽和度`、`中籤率`：歷史統計指標。

## 🚀 環境需求
```bash
pip install pandas
