# 課程資料處理系統

本專案用於爬取、處理和分析學校課程資料，包含資料爬取、教師字典建立和資料清洗三個主要模組。

## 📁 專案結構

```
Final_Project/
├── course_crawler.py            # 課程資料爬蟲
├── teacher_dict_builder.py      # 建立教師字典
├── course_data_processor.py     # 資料處理管道
├── raw_data/                    # 原始資料（CSV 檔案）
├── dict/                        # 教師字典檔案
│   ├── teacher.csv              # 主要教師字典（人工）
│   ├── teacher_dict_auto.csv    # 自動建立的教師字典
│   └── teacher_high_risk.csv    # 需人工確認的高風險教師名單
└── processed_data/              # 處理後的資料
    └── all_courses_*.csv        # 清洗後的完整課程資料
```

## 🚀 使用流程

### 1. 爬取課程資料

執行 `course_crawler.py` 從學校網站爬取課程資料：

```bash
python course_crawler.py
```

**設定說明：**
- `START_YEAR` / `START_SEMESTER`: 起始學期
- `END_YEAR` / `END_SEMESTER`: 結束學期
- `OUTPUT_DIR`: 輸出目錄（預設為 `raw_data`）

**輸出：** 在 `raw_data/` 目錄下產生 `courses_YYYY_S.csv` 檔案

### 2. 建立教師字典

執行 `teacher_dict_builder.py` 自動建立教師字典：

```bash
python teacher_dict_builder.py
```

**功能：**
- 從原始資料中提取教師姓名
- 使用動態規劃（DP）演算法智能分割黏連的教師姓名
- 自動識別三字教師姓名
- 輸出兩個檔案：
  - `teacher_dict_auto.csv`: 自動確認的教師名單
  - `teacher_high_risk.csv`: 需人工確認的高風險名單

**演算法說明：**
- 使用 DP 標記已知教師位置
- 處理 2 字和 3 字教師姓名
- 自動分割黏連的教師姓名（如：`蕭輔力劉少勲` → `蕭輔力`, `劉少勲`）

### 3. 資料清洗

執行 `course_data_processor.py` 進行資料清洗：

```bash
python course_data_processor.py
```

**處理內容：**
1. **課程名稱分割**：將中文和英文課程名稱分離
2. **上課時間解析**：解析多時段上課資訊（如：`(一)01-02 (三)05`）
3. **教師姓名處理**：使用正向最大匹配法分割教師姓名
4. **資料合併**：合併所有學期的資料

**輸出：** 在 `processed_data/` 目錄下產生帶時間戳的 `all_courses_YYYYMMDD_HHMMSS.csv`

### 4. 資料前處理

執行 `clean1.py` 進行深度資料清洗與特徵建構：

```bash
python clean1.py
```

**處理內容：**
1. **課程名稱分割**：將中文和英文課程名稱分離
2. **系所歸戶對照**：依據課程代碼前兩碼（如 54 -> 資工系），自動映射對應的「系所」與「學院」。
3. **數值特徵建構**：
* 計算 飽和度 (Saturation)：登記人數 / 上限人數 (衡量熱門程度)。
* 計算 中籤率 (Success Rate)：選上人數 / 登記人數 (衡量選課難度)。
* 處理 全英語授課：將布林值轉換為數值特徵 (0/1)。
4. **時間格式清洗**：將原始 (一)01-02 格式轉換為數值化的 星期_數值、起始節次、結束節次。

**輸出：** 在 `processed_data/` 目錄下產生帶時間戳的 `clean_course.csv`

### 5. 關聯性法則分群

執行 `kmeans_cluster.py` 進行資料清洗：

```bash
python kmeans_cluster.py
```

**分析方法：**
1. **特徵選取**：使用 學分、上限人數、飽和度、中籤率、全英數值、起始節次 等六大維度。
2. **資料標準化**：解析多時段上課資訊（如：`(一)01-02 (三)05`）
3. **教師姓名處理**：使用 StandardScaler 將不同單位的數據（如人數 vs 學分）縮放至同一尺度。
4. **K-Means 演算法**：設定 K=5 將全校課程分為五種生態類群。

分群意義 (Cluster 0-4)：
* Cluster 0 (一般課程)：數量最多，供需平衡的課程。
* Cluster 1 (全英授課)：全英語授課 (EMI) 的專屬群集。
* Cluster 2 (冷門課程)：中籤率異常高 (>100%)，通常為人工加簽或灌檔課程。
* Cluster 3 (研究所)：人數上限少、學分較高的進階課程。
* Cluster 4 (搶手熱門)：飽和度極高、中籤率低的秒殺課程。

**輸出：** 在 `processed_data/` 目錄下產生帶時間戳的 `clustered_courses.csv`

## 📋 資料欄位說明

### 原始資料欄位（raw_data）
- 課程代碼、課程名稱、教師姓名
- 上課節次+地點、學分、人數等

### 處理後資料欄位（processed_data）
- `學年度`、`學期`：從檔名提取
- `中文課程名稱`、`英文課程名稱`：分割後的課程名稱
- `星期`、`起始節次`、`結束節次`、`上課地點`：解析後的時間地點資訊
- `教師列表`：分割後的教師姓名（以逗號分隔）

## 🔧 技術細節

### 課程名稱分割邏輯
- 使用狀態掃描法
- 處理中文 + (級別/代碼/括號) + 英文的格式
- 自動識別英文標題起點（大寫字母或數字+字母組合）

### 教師姓名分割
- **正向最大匹配（Forward Maximum Matching）**
- 支援字典查詢，自動分割黏連姓名
- 處理特殊情況（校際教師、校外教師）

### 時間地點解析
- 支援多時段格式：`(一)01-02 (三)05`
- 使用正則表達式提取星期、節次和地點
- 自動展開為多筆記錄（Explode）

## 📦 依賴套件

```txt
pandas
beautifulsoup4
requests
lxml
```

安裝方式：
```bash
pip install pandas beautifulsoup4 requests lxml
```

## ⚠️ 注意事項

1. **教師字典**：執行 `course_data_processor.py` 前需確保 `dict/teacher.csv` 存在
2. **檔案編碼**：所有 CSV 檔案使用 `utf-8-sig` 編碼
3. **網路爬蟲**：`course_crawler.py` 需要網路連線，請遵守網站使用規範
4. **資料備份**：建議定期備份 `raw_data` 和 `processed_data` 目錄