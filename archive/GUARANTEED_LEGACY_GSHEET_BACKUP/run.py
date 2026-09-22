# -*- coding: utf-8 -*-

r"""
BBK DAILY PIPELINE
Lokasi: Otomatis mendeteksi folder tempat script berada
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

# ✅ PERBAIKAN 1: Path otomatis menunjuk ke direktori tempat run.py berada
BASE_DIR = Path(__file__).resolve().parent
LAST_SUCCESS_FILE = BASE_DIR / "last_success.txt"

# ================= RUN COMMAND =================

def run(cmd):
    print(f"\n>>> RUNNING: {cmd}\n")
    # Menjalankan perintah dengan cwd diset ke BASE_DIR
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

    # 1. KONDISI INPUT MANUAL (Override semuanya)
    if user_args:
        args = " ".join(user_args)
        print(f"📅 Manual Date Running dengan argumen: {args}")
    
    # 2. KONDISI OTOMATIS (Baca last_success.txt)
    else:
        if LAST_SUCCESS_FILE.exists():
            with open(LAST_SUCCESS_FILE, "r") as f:
                last_date_str = f.read().strip()
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=tz)
                start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        
        end_date = now.strftime("%Y-%m-%d")
        args = f"--start {start_date} --end {end_date}"
        print(f"💡 Automatic Running: {start_date} sampai {end_date}")

    # ✅ PERBAIKAN 2: Gunakan sys.executable agar memanggil executable Python yang sedang aktif
    python_exe = f'"{sys.executable}"'

    # STEP 1 — FETCH TELEGRAM
    print("\n==============================")
    print("STEP 1 — FETCH TELEGRAM")
    print("==============================\n")
    run(f"{python_exe} telethon_fetch.py {args}")

    # STEP 2 — PARSE TO RAW_INVENTORY
    print("\n==============================")
    print("STEP 2 — PARSE TO RAW_INVENTORY")
    print("==============================\n")
    run(f"{python_exe} telegram_parser_to_gsheet.py")
    
    # Update last_success.txt dengan tanggal hari ini
    with open(LAST_SUCCESS_FILE, "w") as f:
        f.write(now.strftime("%Y-%m-%d"))

    print("\n==============================")
    print("✅ PIPELINE COMPLETE")
    print("==============================\n")

if __name__ == "__main__":
    main()