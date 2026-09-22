# -*- coding: utf-8 -*-
"""
👑 BBKitchen Sovereign 1-Click Pipeline Runner (run.py)
Usage:
  python run.py                     # Otomatis fetch delta baru -> normalize AI -> sync Turso
  python run.py --start 2026-09-08 --end 2026-09-22   # Fetch rentang tanggal spesifik (H-14)
  python run.py --dry-run           # Simulasi tanpa commit ke Turso
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
CORE_DIR = BASE_DIR / "core"
LAST_SUCCESS_FILE = BASE_DIR / "last_success.txt"
PYTHON_EXE = f'"{sys.executable}"'
LOCAL_TZ = ZoneInfo("Asia/Jakarta")

def run_step(title, cmd):
    print(f"\n=======================================================")
    print(f"🚀 {title}")
    print(f"=======================================================")
    print(f"Executing: {cmd}\n")
    res = subprocess.run(cmd, shell=True, cwd=BASE_DIR)
    if res.returncode != 0:
        print(f"\n❌ [ERROR] Step failed with exit code: {res.returncode}")
        sys.exit(res.returncode)

def main():
    user_args = sys.argv[1:]
    now = datetime.now(LOCAL_TZ)

    # 1. Tentukan rentang tanggal
    if user_args and any(arg in ["--start", "--date"] for arg in user_args):
        fetch_args = " ".join(user_args)
        print(f"📅 Manual Date Running: {fetch_args}")
    else:
        if LAST_SUCCESS_FILE.exists():
            with open(LAST_SUCCESS_FILE, "r", encoding="utf-8") as f:
                last_date_str = f.read().strip()
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
                start_date = (last_date - timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                start_date = (now - timedelta(days=14)).strftime("%Y-%m-%d")
        else:
            # Default H-14
            start_date = (now - timedelta(days=14)).strftime("%Y-%m-%d")
        
        end_date = now.strftime("%Y-%m-%d")
        fetch_args = f"--start {start_date} --end {end_date}"
        print(f"💡 Automatic Incremental Range: {start_date} sampai {end_date} (WIB)")

    # STEP 1: FETCH TELEGRAM RAW
    fetch_script = CORE_DIR / "telethon_fetch.py"
    run_step("STEP 1/3 — FETCH RAW TELEGRAM & PHOTOS", f"{PYTHON_EXE} {fetch_script} {fetch_args}")

    # STEP 2: NORMALIZE WITH AI GATEWAY & WATERMARK WEBP
    pipeline_script = BASE_DIR / "bbk_pipeline.py"
    run_step("STEP 2/3 — AI NORMALIZATION, SSOT & WEBP WATERMARK", f"{PYTHON_EXE} {pipeline_script} normalize")

    # STEP 3: SYNC TO TURSO CLOUD EDGE
    run_step("STEP 3/3 — SYNC CATALOG & MASTERS TO TURSO CLOUD EDGE", f"{PYTHON_EXE} {pipeline_script} sync --dirty --master")

    # Update last_success.txt
    with open(LAST_SUCCESS_FILE, "w", encoding="utf-8") as f:
        f.write(now.strftime("%Y-%m-%d"))

    print("\n=======================================================")
    print("✅ 1-CLICK SOVEREIGN PIPELINE RUN COMPLETED SUCCESSFULLY!")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
