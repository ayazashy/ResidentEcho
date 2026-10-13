#!/usr/bin/env python3
"""
ResidentEcho Telegram Chat Anonymizer & Normalizer
Anonymizes Telegram user IDs in 'u' and masks all phone numbers and personal usernames in 't'.
Overwrites compressed.json and compressed.json.gz with minified, fully anonymized data.
"""

import os
import re
import json
import gzip

INPUT_OUTPUT_JSON = os.path.join(
    os.path.dirname(__file__), "ChatExport_2026-10-13", "compressed.json"
)
OUTPUT_GZ = os.path.join(
    os.path.dirname(__file__), "ChatExport_2026-10-13", "compressed.json.gz"
)
OUTPUT_MAPPING_VAULT = os.path.join(
    os.path.dirname(__file__), "ChatExport_2026-10-13", ".user_mapping_vault.json"
)



# Regex patterns
SAUDI_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:(?:\+?966|00966)[\s\-]?)?(?:0?5\d)(?:[\s\-]?\d){7}(?!\d)"
)
INTL_PHONE_PATTERN = re.compile(
    r"(?<!\d)\+\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4}(?!\d)"
)
WAME_PATTERN = re.compile(
    r"((?:https?://)?wa\.me/(?:p/\d+/)?)\+?\d+"
)
MENTION_PATTERN = re.compile(r"@([a-zA-Z0-9_]{3,})")


def anonymize_text(text: str) -> str:
    """Mask phone numbers and personal usernames inside Telegram text."""
    if not text:
        return ""

    # 1. Mask wa.me links
    text = WAME_PATTERN.sub(r"\1[رقم_جوال]", text)

    # 2. Protect URLs
    urls = []

    def protect_url(match):
        urls.append(match.group(0))
        return f"__PROTECTED_URL_{len(urls)-1}__"

    text = re.sub(r"https?://\S+", protect_url, text)

    # 3. Mask phone numbers
    text = SAUDI_PHONE_PATTERN.sub("[رقم_جوال]", text)
    text = INTL_PHONE_PATTERN.sub("[رقم_جوال]", text)

    # 4. Mask personal mentions (preserve only automated service bots)
    def mask_mention(match):
        handle = match.group(1).lower()
        if handle.endswith("bot"):
            return match.group(0)
        return "@مستخدم"

    text = MENTION_PATTERN.sub(mask_mention, text)

    # 5. Restore URLs
    for idx, u in enumerate(urls):
        text = text.replace(f"__PROTECTED_URL_{idx}__", u)

    # 6. Clean bidi markers
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", text)

    return text.strip()


def main():
    print(f"جاري قراءة ملف شات التليغرام:\n{INPUT_OUTPUT_JSON}")
    if not os.path.exists(INPUT_OUTPUT_JSON):
        print("خطأ: الملف غير موجود!")
        return

    with open(INPUT_OUTPUT_JSON, "r", encoding="utf-8") as f:
        messages = json.load(f)

    total_msgs = len(messages)
    print(f"إجمالي الرسائل المحملة: {total_msgs:,}")

    # Build user mapping
    unique_users = sorted(
        list(set(m["u"] for m in messages if m.get("u") is not None))
    )
    print(f"إجمالي المستخدمين الفريدين الفعليين: {len(unique_users):,}")

    user_mapping = {}
    next_user_id = 1000000001
    for u in unique_users:
        user_mapping[u] = next_user_id
        next_user_id += 1

    # Save mapping vault securely
    with open(OUTPUT_MAPPING_VAULT, "w", encoding="utf-8") as vf:
        json.dump(user_mapping, vf, ensure_ascii=False, indent=2)

    # Anonymize all messages
    masked_phone_count = 0
    anonymized_messages = []

    for msg in messages:
        raw_u = msg.get("u")
        anon_u = user_mapping.get(raw_u, raw_u)
        raw_text = msg.get("t", "")

        anon_text = anonymize_text(raw_text)

        item = {
            "i": msg["i"],
            "d": msg["d"],
            "u": anon_u,
            "t": anon_text,
        }
        if "r" in msg:
            item["r"] = msg["r"]

        anonymized_messages.append(item)

    print(f"جاري حفظ الملف المخفف والمعمى (JSON): {INPUT_OUTPUT_JSON}")
    json_bytes = json.dumps(
        anonymized_messages, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    with open(INPUT_OUTPUT_JSON, "wb") as f:
        f.write(json_bytes)

    json_size_mb = os.path.getsize(INPUT_OUTPUT_JSON) / (1024 * 1024)
    print(f"حجم الملف المخفف (JSON): {json_size_mb:.2f} MB")

    print(f"جاري ضغط الملف إلى GZIP (أقصى ضغط 9): {OUTPUT_GZ}")
    gz_bytes = gzip.compress(json_bytes, compresslevel=9)
    with open(OUTPUT_GZ, "wb") as f:
        f.write(gz_bytes)

    gz_size_mb = os.path.getsize(OUTPUT_GZ) / (1024 * 1024)
    print(f"حجم الملف المضغوط (GZ): {gz_size_mb:.2f} MB")

    print("\n--- اكتملت عملية تعمية التليغرام بنجاح ---")
    print(f"إجمالي الرسائل: {len(anonymized_messages):,}")
    print(f"إجمالي المستخدمين المعمين: {len(user_mapping):,}")
    print(f"نطاق معرفات المستخدمين: 1000000001 إلى {next_user_id - 1}")

    print("\nعينة من أول رسالتين بعد التعمية:")
    for m in anonymized_messages[:2]:
        print(m)


if __name__ == "__main__":
    main()
