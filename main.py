#!/usr/bin/env python3
"""Course Master - 智慧選課輔助系統主入口點"""

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
SRC_DIR = BASE_DIR / "src"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.common import setup_logging

def main():
    parser = argparse.ArgumentParser(description="Course Master - 智慧選課輔助系統")
    parser.add_argument(
        "command",
        choices=["crawl", "process", "build-dict", "api", "all"],
        help="要執行的命令"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日誌級別"
    )

    args = parser.parse_args()

    import logging
    logging.basicConfig(level=getattr(logging, args.log_level))

    if args.command == "crawl":
        from crawler.crawler import main as crawl_main
        crawl_main()

    elif args.command == "process":
        from processor.data_processor import main as process_main
        process_main()

    elif args.command == "build-dict":
        from processor.teacher_dict_builder import main as dict_main
        dict_main()

    elif args.command == "api":
        from api.app import main as api_main
        api_main()

    elif args.command == "all":
        print("開始執行完整流程...")
        try:
            print("1. 爬取課程數據...")
            from crawler.crawler import main as crawl_main
            crawl_main()

            print("2. 構建教師字典...")
            from processor.teacher_dict_builder import main as dict_main
            dict_main()

            print("3. 處理課程數據...")
            from processor.data_processor import main as process_main
            process_main()

            print("4. 啟動 API 服務器...")
            from api.app import main as api_main
            api_main()

        except Exception as e:
            print(f"執行失敗: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
