#!/usr/bin/env python3
"""
ResidentEcho - Daily Message Splitter & Merger
Merges Telegram and WhatsApp anonymized chat history and splits them chronologically
into daily JSON files (YYYY-MM-DD.json) within the 'daily_messages/' directory.
"""

import os
import json
from collections import defaultdict

BASE_DIR = os.path.dirname(__file__)
TG_FILE = os.path.join(BASE_DIR, "ChatExport_2026-10-13", "compressed.json")
WA_FILE = os.path.join(BASE_DIR, "ChatExport2_2026-10-13", "compressed.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "daily_messages")
INDEX_FILE = os.path.join(OUTPUT_DIR, "_index.json")


def load_dataset(file_path, source_tag):
    """Load messages and tag them with source platform ('tg' or 'wa')."""
    print(f"جاري قراءة بيانات {source_tag.upper()} من:\n{file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"الملف غير موجود: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tagged_messages = []
    for msg in data:
        item = {
            "s": source_tag,  # 'tg' for Telegram, 'wa' for WhatsApp
            "i": msg["i"],
            "d": msg["d"],
            "u": msg["u"],
            "t": msg.get("t", ""),
        }
        if "r" in msg:
            item["r"] = msg["r"]
        tagged_messages.append(item)

    print(f"تم تحميل {len(tagged_messages):,} رسالة من {source_tag.upper()}.")
    return tagged_messages


def main():
    print("=== بدء عملية دمج وتقسيم الرسائل بحسب الأيام (Daily Partitioning) ===")

    # 1. Load both sources
    tg_messages = load_dataset(TG_FILE, "tg")
    wa_messages = load_dataset(WA_FILE, "wa")

    total_combined = len(tg_messages) + len(wa_messages)
    print(f"\nإجمالي الرسائل المراد دمجها: {total_combined:,} رسالة.")

    # 2. Group by date (YYYY-MM-DD)
    print("\nجاري تجميع وفرز الرسائل زمنياً لكل يوم...")
    daily_groups = defaultdict(list)
    daily_counts = defaultdict(lambda: {"tg": 0, "wa": 0})

    for msg in tg_messages:
        date_str = msg["d"][:10]
        daily_groups[date_str].append(msg)
        daily_counts[date_str]["tg"] += 1

    for msg in wa_messages:
        date_str = msg["d"][:10]
        daily_groups[date_str].append(msg)
        daily_counts[date_str]["wa"] += 1

    # 3. Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sorted_dates = sorted(daily_groups.keys())
    print(
        f"تم تحديد {len(sorted_dates)} يوماً فريداً (من {sorted_dates[0]} إلى {sorted_dates[-1]})."
    )

    # 4. Sort each day chronologically and write to JSON
    print(f"\nجاري حفظ الملفات اليومية داخل المجلد: {OUTPUT_DIR}/ ...")
    index_entries = []

    for date_str in sorted_dates:
        day_msgs = daily_groups[date_str]
        # Sort chronologically by ISO timestamp string 'd', then by 'i'
        day_msgs.sort(key=lambda m: (m["d"], m["i"]))

        out_path = os.path.join(OUTPUT_DIR, f"{date_str}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(day_msgs, f, ensure_ascii=False, indent=2)

        file_size_kb = os.path.getsize(out_path) / 1024
        tg_cnt = daily_counts[date_str]["tg"]
        wa_cnt = daily_counts[date_str]["wa"]

        index_entries.append(
            {
                "date": date_str,
                "file": f"{date_str}.json",
                "total_messages": len(day_msgs),
                "telegram": tg_cnt,
                "whatsapp": wa_cnt,
                "size_kb": round(file_size_kb, 1),
            }
        )

    # 5. Write master index file
    index_data = {
        "metadata": {
            "total_days": len(sorted_dates),
            "start_date": sorted_dates[0],
            "end_date": sorted_dates[-1],
            "total_messages": total_combined,
            "total_telegram": len(tg_messages),
            "total_whatsapp": len(wa_messages),
        },
        "days": index_entries,
    }

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    print(f"\nتم إنشاء فهرس السجلات اليومية الرئيسي: {INDEX_FILE}")
    print("\n--- اكتملت عملية التقسيم والدمج بنجاح ---")
    print(f"عدد الأيام المقسمة: {len(sorted_dates)} يوم.")
    print(f"المجلد النهائي: {OUTPUT_DIR}/")
    print(f"عينة من أول يوم ({sorted_dates[0]}): {len(daily_groups[sorted_dates[0]])} رسالة.")
    print(
        f"عينة من آخر يوم ({sorted_dates[-1]}): {len(daily_groups[sorted_dates[-1]])} رسالة (تليغرام: {daily_counts[sorted_dates[-1]]['tg']}، واتساب: {daily_counts[sorted_dates[-1]]['wa']})."
    )


if __name__ == "__main__":
    main()
