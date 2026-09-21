# -*- coding: utf-8 -*-

r"""
BBK DAILY PIPELINE (CLOUD VERSION)
Lokasi: Dibuat khusus untuk dijalankan di GitHub Actions
"""

import sys
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Path otomatis menunjuk ke direktori tempat run_cloud.py berada
BASE_DIR = Path(__file__).resolve().parent

# ================= RUN COMMAND =================

def run(cmd):
    print(f"\n>>> RUNNING: {cmd}\n")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=BASE_DIR
    )

    if result.returncode != 0:
        print("\n❌ ERROR: COMMAND FAILED\n")
        sys.exit(result.returncode)

# ================= MAIN =================

def main():
    user_args = sys.argv[1:]
    tz = ZoneInfo("Asia/Jakarta")
    now = datetime.now(tz)

    # 1. KONDISI INPUT MANUAL (Override)
    if user_args:
        args = " ".join(user_args)
        print(f"📅 Manual Date Running (Cloud) dengan argumen: {args}")
    
    # 2. KONDISI OTOMATIS (Default Cloud: Ambil data 2 hari terakhir agar cepat dan aman)
    else:
        start_date = (now - timedelta(days=2)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
        args = f"--start {start_date} --end {end_date}"
        print(f"💡 Automatic Running (Cloud): {start_date} sampai {end_date} (2 Hari Terakhir)")

    python_exe = f'"{sys.executable}"'

    # STEP 1 — FETCH TELEGRAM
    print("\n==============================")
    print("STEP 1 — FETCH TELEGRAM (CLOUD)")
    print("==============================\n")
    run(f"{python_exe} telethon_fetch.py {args}")

    # STEP 2 — PARSE TO RAW_INVENTORY
    print("\n==============================")
    print("STEP 2 — PARSE TO RAW_INVENTORY (CLOUD)")
    print("==============================\n")
    run(f"{python_exe} telegram_parser_to_gsheet.py")

    print("\n==============================")
    print("✅ CLOUD PIPELINE COMPLETE")
    print("==============================\n")

if __name__ == "__main__":
    main()
