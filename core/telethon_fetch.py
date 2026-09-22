# -*- coding: utf-8 -*-

import sys
import json
import argparse
import asyncio

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from telethon import TelegramClient
from tqdm import tqdm

from config_telethon import (
    API_ID,
    API_HASH,
    SESSION_NAME
)

# ================= CONFIG (Jalur Disesuaikan) =================

BASE_DIR = Path(__file__).parent
EXPORT_ROOT = BASE_DIR / "exports"

LOCAL_TZ = ZoneInfo("Asia/Jakarta")

SOURCE_MAP = {
    "GK": -1002479885293,
    "BB": -1001947492349,
    "SM": -1002249769366,
    "BL": -1002221612633,
    "ML": -1002295735681,
    "PY": -1002556966592,
    "PE": -1002471308578,
    "WT": -1002559367434,
    "ON": -1003420173563,
    "RB": -1002405866006,
    "RK": -1004326430608,      # Rizki Kitchen (Rawakalong Bogor)
    "SK": -1003506626675,      # Sanjaya Kitchen (Sawangan Depok)
    "KG": -1002375036806,      # Kitchen Gembel (Pamulang Barat)
}

# ================= ARGUMENT =================

parser = argparse.ArgumentParser()
parser.add_argument("--date", help="YYYY-MM-DD")
parser.add_argument("--start", help="YYYY-MM-DD")
parser.add_argument("--end", help="YYYY-MM-DD")
parser.add_argument("--days", type=int, help="Fetch messages from the last N days (e.g. --days 14)")
args, unknown = parser.parse_known_args()

# ================= DATE =================

def parse_local(dt_str):
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=LOCAL_TZ)

if args.days:
    now_local = datetime.now(LOCAL_TZ)
    start_local = (now_local - timedelta(days=args.days)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
elif args.date:
    start_local = parse_local(args.date).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
elif args.start and args.end:
    start_local = parse_local(args.start).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = parse_local(args.end).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
else:
    # OTOMATIS: Ambil dari jam 00:00:00 H-1 hingga akhir hari ini (WIB)
    now_local = datetime.now(LOCAL_TZ)
    start_local = (now_local - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

START_DATE = start_local.astimezone(timezone.utc)
END_DATE = end_local.astimezone(timezone.utc)

print(f"WIB Range: {start_local.strftime('%Y-%m-%d %H:%M:%S')} -> {end_local.strftime('%Y-%m-%d %H:%M:%S')}")

# ================= TELETHON =================

client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH
)

async def fetch_group(src_code, chat_id):
    out_dir = EXPORT_ROOT / src_code
    out_dir.mkdir(parents=True, exist_ok=True)

    messages = []
    pbar = tqdm(desc=f"Scanning [{src_code}]", unit=" msg", leave=False)

    async for msg in client.iter_messages(chat_id, offset_date=END_DATE):
        pbar.update(1)
        if not msg.date: continue
        if msg.date < START_DATE: break
        if not msg.photo: continue

        photo_path = await msg.download_media(out_dir / f"{msg.id}.jpg")

        messages.append({
            "id": msg.id,
            "grouped_id": msg.grouped_id,
            "type": "message",
            "date": msg.date.isoformat(),
            "date_unixtime": int(msg.date.timestamp()),
            "text": msg.text or "",
            "photo": Path(photo_path).name if photo_path else ""
        })

    pbar.close()

    with open(out_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump({"messages": messages}, f, ensure_ascii=False, indent=2)

    print(f"[{src_code}] Berhasil mengambil {len(messages)} pesan bergambar.")

# ================= MAIN =================

async def main():
    await client.start()
    for src, chat_id in SOURCE_MAP.items():
        await fetch_group(src, chat_id)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
