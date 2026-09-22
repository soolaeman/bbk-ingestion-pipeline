# -*- coding: utf-8 -*-
"""
👑 BBKitchen Sovereign 1-Click Pipeline Runner (run.py)
Usage:
  python run.py                     # Otomatis baca last_success.txt atau H-1 incremental
  python run.py 7                   # Fetch 7 hari kebelakang dari detik ini (H-7 s.d hari ini)
  python run.py 14                  # Fetch 14 hari kebelakang (H-14 s.d hari ini)
  python run.py 2026-09-15          # Fetch tanggal spesifik
  python run.py --start 2026-09-08 --end 2026-09-22   # Rentang tanggal manual
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

    # 1. Parsing argumen fleksibel: Angka (H-X), Tanggal, atau Flag
    if user_args:
        first_arg = user_args[0].strip()

        # Opsi A: User memasukkan angka (Contoh: "python run.py 7" atau "python run.py 14")
        if first_arg.isdigit():
            days_back = int(first_arg)
            start_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
            end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            fetch_args = f"--start {start_date} --end {end_date}"
            print(f"⚡ Shortcut H-{days_back}: Menarik {days_back} hari kebelakang ({start_date} s.d {end_date} WIB)")

        # Opsi B: User memasukkan tanggal YYYY-MM-DD tunggal (Contoh: "python run.py 2026-09-15")
        elif len(first_arg) == 10 and first_arg.count("-") == 2:
            fetch_args = f"--date {first_arg}"
            print(f"📅 Tanggal Spesifik: {first_arg} (WIB)")

        # Opsi C: Flag standar --start / --end
        elif any(arg in ["--start", "--date"] for arg in user_args):
            fetch_args = " ".join(user_args)
            print(f"📅 Manual Arguments: {fetch_args}")
        else:
            fetch_args = " ".join(user_args)
            print(f"⚙️ Custom Arguments: {fetch_args}")

    # Opsi D: Tanpa argumen (Otomatis baca last_success.txt atau H-1)
    else:
        if LAST_SUCCESS_FILE.exists():
            with open(LAST_SUCCESS_FILE, "r", encoding="utf-8") as f:
                last_date_str = f.read().strip()
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
                start_date = (last_date - timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        
        end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        fetch_args = f"--start {start_date} --end {end_date}"
        print(f"💡 Automatic Incremental: {start_date} sampai {end_date} (WIB)")

    # STEP 1: FETCH TELEGRAM RAW
    fetch_script = CORE_DIR / "telethon_fetch.py"
    run_step("STEP 1/3 — FETCH RAW TELEGRAM & PHOTOS (Anti-Duplicate Link)", f"{PYTHON_EXE} {fetch_script} {fetch_args}")

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
