# Course Master — 智慧選課輔助系統

智慧選課輔助系統，提供課程資料爬取、處理、查詢與推薦功能。

## 專案結構

```
Final_Project/
├── main.py                 # 主入口點
├── requirements.txt        # 依賴套件
├── config/                 # 配置目錄
│   ├── __init__.py        # 配置匯出
│   ├── paths.py           # 路徑配置
│   ├── crawler.py         # 爬蟲配置
│   ├── api.py             # API 配置
│   └── logging_config.py  # 日誌配置
├── data/                   # 資料目錄
│   ├── raw/               # 原始爬取資料
│   ├── processed/         # 處理後的資料
│   └── dict/              # 字典檔案（教師、科系映射）
├── src/                    # 原始碼
│   ├── api/               # API 模組
│   │   └── app.py         # FastAPI 應用
│   ├── crawler/           # 爬蟲模組
│   │   └── crawler.py     # 課程爬蟲
│   ├── processor/         # 資料處理模組
│   │   ├── data_processor.py      # 資料處理器
│   │   ├── teacher_dict_builder.py # 教師字典構建器
│   │   └── department_mapper.py   # 科系映射器
│   ├── utils/             # 工具模組
│   │   ├── common.py      # 共用工具
│   │   └── io.py          # I/O 工具
│   └── config.py          # Config shim
├── scripts/               # 維護腳本
│   ├── print_config.py           # 列印配置
│   ├── check_processed_fields.py # 檢查處理後欄位
│   └── manual_recommend_test.py  # 推薦測試
├── web/                   # 前端檔案
│   ├── index.html
│   └── assets/
│       ├── css/
│       └── js/
└── logs/                  # 日誌目錄
```

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 執行完整流程

```bash
# 執行完整流程（爬取 → 構建字典 → 處理 → 啟動 API）
python main.py all
```

### 3. 分步執行

```bash
# 爬取課程資料
python main.py crawl

# 構建教師字典
python main.py build-dict

# 處理資料
python main.py process

# 啟動 API 服務
python main.py api
```

## 主要功能

### 資料爬取
- 自動爬取多學期課程資料
- 處理 ASP.NET 表單
- 解析課程表格與教學大綱連結

### 資料處理
- 課程名稱分割（中英文）
- 教師姓名智能解析
- 上課時間與地點解析
- 科系映射（學院、科系、年級、班級）

### API 服務
- 課程搜尋與過濾
- 智慧推薦系統
- 歷年資料查詢
- 統計資料獲取

### Web 介面
- 完整課表系統（12 節次）
- 一鍵導入班級課程
- 智慧推薦功能
- 歷年資料查詢
- 缺額追蹤功能

## 資料流程

```
原始網站 → 爬蟲 → 原始 CSV → 資料處理 → 清理資料 → API → Web 介面
```

## 技術棧

- **後端**：Python 3.8+
- **Web 框架**：FastAPI
- **資料處理**：pandas
- **爬蟲**：requests + BeautifulSoup4
- **前端**：HTML5 + Bootstrap 5 + JavaScript

## 配置說明

主要配置位於 `config/` 目錄：

- `paths.py`：檔案路徑配置
- `crawler.py`：爬蟲參數（學期範圍、URL 等）
- `api.py`：API 伺服器配置
- `logging_config.py`：日誌配置

## 維護腳本

- `scripts/print_config.py`：檢查載入的配置
- `scripts/check_processed_fields.py`：驗證處理後資料的欄位
- `scripts/manual_recommend_test.py`：測試推薦 API

## 注意事項

- 爬蟲會發出網路請求，執行前請確認網路可用且符合目標網站使用規範
- 建議先使用 `scripts/check_processed_fields.py` 檢查處理後資料再啟動 API
- 教師字典需要人工審核高風險項目

## 授權

本專案採用 MIT 授權。
