# 爬蟲相關設定
BASE_URL = "https://webap0.ncue.edu.tw/DEANV2/Other/OB010"
BASE_DOMAIN = "https://webap0.ncue.edu.tw"
START_YEAR = 111
START_SEMESTER = 1
END_YEAR = 115
END_SEMESTER = 1
CLS_BRANCH = ""
# 查詢頁已改為 ASP.NET MVC，部別只能分開查（D=日間部、N=夜間部），爬完再合併
CLS_BRANCHES = ["D", "N"]
HTML_PARSER = "lxml"
REQUEST_DELAY_SEC = 1.0
