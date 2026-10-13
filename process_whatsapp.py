#!/usr/bin/env python3
"""
ResidentEcho WhatsApp Chat Anonymizer & Normalizer
Converts WhatsApp raw export to the exact compressed.json schema used by Telegram:
[
  {
    "i": <message_id: int>,
    "d": "<ISO_8601_date: str>",
    "u": <anonymized_user_id: int>,
    "t": "<anonymized_text: str>"
  },
  ...
]
"""

import os
import re
import json
import gzip
from datetime import datetime

INPUT_FILE = os.path.join(
    os.path.dirname(__file__),
    "ChatExport2_2026-10-13",
    "WhatsApp Chat with تجمع طلاب السكن ✅.txt",
)
OUTPUT_JSON = os.path.join(
    os.path.dirname(__file__), "ChatExport2_2026-10-13", "compressed.json"
)
OUTPUT_GZ = os.path.join(
    os.path.dirname(__file__), "ChatExport2_2026-10-13", "compressed.json.gz"
)
OUTPUT_MAPPING_VAULT = os.path.join(
    os.path.dirname(__file__), "ChatExport2_2026-10-13", ".user_mapping_vault.json"
)

# Date header regex: e.g. "9/13/25, 10:39 PM - " or "10/13/26, 1:25 AM - "
HEADER_REGEX = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[\u202f\s]*(?:AM|PM)))\s*-\s*(.*)$"
)

# Known personal names identified from the group participants/moderators
KNOWN_NAMES = [
    "عادل محماس الرقاص",
    "عادل محماس",
    "احمد توفيق احمد مطر",
    "احمد توفيق",
    "البراء عواجي",
    "تميم السلامة",
    "انس العوفي",
    "أنس العوفي",
    "أسامة النغيمش",
    "اسامة النغيمش",
    "سعد منيف سعد العنزي",
    "سعد منيف العنزي",
    "سعيد عبدان الزهراني",
    "سعيد الزهراني",
    "ضياء الصائغ",
    "عبدالله يوسف العلي العباد",
    "عبدالله العباد",
    "عمر منير فرج العتيبي",
    "عمر العتيبي",
    "فيصل الحارثي",
    "عبد الرحمن بن محمد الشريف",
    "عبدالرحمن بن محمد الشريف",
    "علي بن عبد الله بن محمد الهاشم",
    "علي بن عبدالله بن محمد الهاشم",
    "مازن بن خالد بن عناد السلطاني العنزي",
    "مازن العنزي",
    "منصور بن محمد بن منصور ل بشير",
    "Yazan A.S",
    "عبدالله التميمي",
    "Kareem Khaled",
    "@Abdulwahhab_Elshaarawy",
    "@qABiLx",
    "@mohanadhafiz",
]
# Sort longer phrases first to avoid partial substring replacements
KNOWN_NAMES.sort(key=lambda x: len(x), reverse=True)


def is_system_message(content: str) -> bool:
    """Detect WhatsApp system status messages."""
    if ":" not in content:
        return True
    # Edge case: contact name with colon in an added event (e.g. 'added ...: ...')
    if " added " in content and (
        content.startswith("\u200e\u202b") or " / " in content
    ):
        return True
    return False


def clean_sender_raw(s: str) -> str:
    """Normalize raw sender string."""
    s = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s).strip()
    s = s.lstrip("~").strip()
    # Normalize phone numbers
    if re.search(r"^\+?\d[\d\s\-]+$", s):
        s = re.sub(r"[\s\-]", "", s)
    return s


def parse_date_to_iso(date_str: str, time_str: str) -> str:
    """Convert WhatsApp date/time into ISO-8601 string (YYYY-MM-DDTHH:MM:SS)."""
    parts = date_str.split("/")
    month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
    if year < 100:
        year += 2000
    t_clean = time_str.replace("\u202f", " ").strip()
    dt = datetime.strptime(
        f"{year}-{month:02d}-{day:02d} {t_clean}", "%Y-%m-%d %I:%M %p"
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def anonymize_message_text(text: str) -> str:
    """Mask phone numbers, mentions, and personal names inside message text."""
    if not text:
        return ""
    if text.strip() == "<Media omitted>":
        return ""

    # Remove trailing edited tag
    text = re.sub(r"\s*<This message was edited>\s*$", "", text)

    # 1. Anonymize WhatsApp mentions: @\u2068...\u2069 or @+966...
    text = re.sub(r"@[\u2068\u200e]*[^\u2069\n]+[\u2069\u200e]*", "@مستخدم", text)

    # 2. Mask wa.me links
    text = re.sub(
        r"((?:https?://)?wa\.me/(?:p/\d+/)?)\+?\d+", r"\1[رقم_جوال]", text
    )

    # 3. Protect standard URLs (e.g., twitter/X status links, forms)
    urls = []

    def protect_url(match):
        urls.append(match.group(0))
        return f"__PROTECTED_URL_{len(urls)-1}__"

    text = re.sub(r"https?://\S+", protect_url, text)

    # 4. Mask phone numbers
    # Saudi mobile formats: 05XXXXXXXX, +966 5X XXX XXXX, etc.
    saudi_pattern = re.compile(
        r"(?<!\d)(?:(?:\+?966|00966)[\s\-]?)?(?:0?5\d)(?:[\s\-]?\d){7}(?!\d)"
    )
    text = saudi_pattern.sub("[رقم_جوال]", text)

    # International phone formats: +XXX...
    intl_pattern = re.compile(
        r"(?<!\d)\+\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4}(?!\d)"
    )
    text = intl_pattern.sub("[رقم_جوال]", text)

    # 5. Mask known personal names
    for name in KNOWN_NAMES:
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        text = pattern.sub("[مستخدم]", text)

    # 6. Restore protected URLs
    for idx, u in enumerate(urls):
        text = text.replace(f"__PROTECTED_URL_{idx}__", u)

    # 7. Clean invisible bidi markers
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", text)

    return text.strip()


def main():
    print(f"جاري قراءة ملف محادثة الواتساب:\n{INPUT_FILE}")
    if not os.path.exists(INPUT_FILE):
        print("خطأ: الملف غير موجود!")
        return

    raw_size_mb = os.path.getsize(INPUT_FILE) / (1024 * 1024)
    print(f"حجم الملف الأصلي: {raw_size_mb:.2f} MB")

    raw_messages = []
    current_msg = None
    system_messages_count = 0

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.rstrip("\r\n")
            m = HEADER_REGEX.match(line_str)
            if m:
                content = m.group(3)
                if is_system_message(content):
                    system_messages_count += 1
                    current_msg = None
                    continue

                date_part, time_part = m.group(1), m.group(2)
                iso_date = parse_date_to_iso(date_part, time_part)
                sender_raw, body_raw = content.split(":", 1)

                current_msg = {
                    "d": iso_date,
                    "sender": clean_sender_raw(sender_raw),
                    "text": body_raw.lstrip(" "),
                }
                raw_messages.append(current_msg)
            else:
                # Continuation of multi-line message
                if current_msg is not None:
                    current_msg["text"] += "\n" + line_str

    print(f"تم استخراج {len(raw_messages)} رسالة محادثة صالحة.")
    print(f"تم استبعاد {system_messages_count} رسالة نظام وتنبيهات.")

    # Build anonymized user mapping:
    # Users will receive deterministic IDs: 2000000001, 2000000002, ...
    user_mapping = {}
    next_user_id = 2000000001

    # Deterministic ordering by sender name
    unique_senders = sorted(list(set(m["sender"] for m in raw_messages)))
    for sender in unique_senders:
        user_mapping[sender] = next_user_id
        next_user_id += 1

    print(
        f"تم تعمية وتعيين معرفات لـ {len(user_mapping)} مستخدم فريد بنجاح."
    )

    # Save mapping vault securely
    with open(OUTPUT_MAPPING_VAULT, "w", encoding="utf-8") as vf:
        json.dump(user_mapping, vf, ensure_ascii=False, indent=2)

    # Process and build final compressed items
    cleaned_messages = []
    for idx, msg in enumerate(raw_messages, start=1):
        anonymized_text = anonymize_message_text(msg["text"])
        user_id = user_mapping[msg["sender"]]

        item = {
            "i": idx,
            "d": msg["d"],
            "u": user_id,
            "t": anonymized_text,
        }
        cleaned_messages.append(item)

    print(f"جاري حفظ الملف المضغوط (JSON): {OUTPUT_JSON}")
    # Write minified JSON
    json_bytes = json.dumps(
        cleaned_messages, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    with open(OUTPUT_JSON, "wb") as f:
        f.write(json_bytes)

    json_size_mb = os.path.getsize(OUTPUT_JSON) / (1024 * 1024)
    print(f"حجم الملف المخفف (JSON): {json_size_mb:.2f} MB")

    print(f"جاري ضغط الملف إلى GZIP (أقصى مستوى ضغط 9): {OUTPUT_GZ}")
    gz_bytes = gzip.compress(json_bytes, compresslevel=9)
    with open(OUTPUT_GZ, "wb") as f:
        f.write(gz_bytes)

    gz_size_mb = os.path.getsize(OUTPUT_GZ) / (1024 * 1024)
    print(f"حجم الملف المضغوط (GZ): {gz_size_mb:.2f} MB")

    print("\n--- الإحصائيات والنتائج النهائية ---")
    print(f"إجمالي الرسائل المعالجة: {len(cleaned_messages):,}")
    print(f"إجمالي المستخدمين المعمين: {len(user_mapping):,}")
    print(f"الحجم الأصلي (TXT):       {raw_size_mb:.2f} MB")
    print(
        f"المخفف والمعمى (JSON):     {json_size_mb:.2f} MB (توفير: {((1 - json_size_mb / raw_size_mb) * 100):.1f}%)"
    )
    print(
        f"المضغوط (GZ):              {gz_size_mb:.2f} MB (توفير: {((1 - gz_size_mb / raw_size_mb) * 100):.1f}%)"
    )

    print("\nعينة من أول رسالتين:")
    for m in cleaned_messages[:2]:
        print(m)

    print("\nعينة من آخر رسالتين:")
    for m in cleaned_messages[-2:]:
        print(m)


if __name__ == "__main__":
    main()
