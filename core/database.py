"""
core/database.py
================
SQLite database for OSINT profiles.
Supports 40+ fields per target with full CRUD.
"""

import sqlite3
import json
import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict


# ── All 40+ OSINT fields grouped by category ─────────────────────────────────

FIELD_GROUPS = {
    "🪪 الهوية الشخصية": [
        ("full_name",        "الاسم الكامل",          "text",     ""),
        ("alias",            "الاسماء المستعارة",      "text",     ""),
        ("gender",           "الجنس",                  "choice",   ["ذكر","أنثى","غير محدد"]),
        ("dob",              "تاريخ الميلاد",          "date",     ""),
        ("age",              "العمر",                  "number",   ""),
        ("nationality",      "الجنسية",                "text",     ""),
        ("national_id",      "رقم الهوية الوطنية",     "text",     ""),
        ("passport",         "رقم الجواز",             "text",     ""),
        ("marital_status",   "الحالة الاجتماعية",      "choice",   ["أعزب","متزوج","مطلق","أرمل"]),
        ("religion",         "الديانة",                "text",     ""),
    ],
    "📞 بيانات التواصل": [
        ("phone_primary",    "الهاتف الرئيسي",         "phone",    ""),
        ("phone_secondary",  "الهاتف الثانوي",         "phone",    ""),
        ("phone_whatsapp",   "واتساب",                 "phone",    ""),
        ("email_primary",    "البريد الإلكتروني",      "email",    ""),
        ("email_secondary",  "بريد ثانوي",             "email",    ""),
        ("telegram",         "تيليجرام",               "text",     ""),
    ],
    "📍 العناوين والمواقع": [
        ("address_current",  "العنوان الحالي",         "textarea", ""),
        ("address_previous", "العنوان السابق",         "textarea", ""),
        ("city",             "المدينة",                "text",     ""),
        ("country",          "الدولة",                 "text",     ""),
        ("coordinates",      "الإحداثيات GPS",         "text",     ""),
        ("workplace_addr",   "عنوان العمل",            "textarea", ""),
    ],
    "🌐 الحضور الرقمي": [
        ("facebook",         "فيسبوك",                 "url",      ""),
        ("instagram",        "إنستجرام",               "url",      ""),
        ("twitter",          "تويتر / X",              "url",      ""),
        ("linkedin",         "لينكدإن",                "url",      ""),
        ("tiktok",           "تيك توك",                "url",      ""),
        ("youtube",          "يوتيوب",                 "url",      ""),
        ("snapchat",         "سناب شات",               "text",     ""),
        ("website",          "الموقع الشخصي",          "url",      ""),
        ("ip_addresses",     "عناوين IP",              "textarea", ""),
        ("usernames",        "أسماء المستخدم",         "textarea", ""),
    ],
    "💼 المهنة والتعليم": [
        ("occupation",       "المهنة",                 "text",     ""),
        ("employer",         "جهة العمل",              "text",     ""),
        ("education",        "المؤهل التعليمي",        "text",     ""),
        ("skills",           "المهارات",               "textarea", ""),
        ("languages",        "اللغات",                 "text",     ""),
        ("income_range",     "نطاق الدخل",             "text",     ""),
    ],
    "🚗 الممتلكات والمركبات": [
        ("vehicles",         "المركبات",               "textarea", ""),
        ("plate_numbers",    "أرقام اللوحات",          "textarea", ""),
        ("properties",       "العقارات",               "textarea", ""),
        ("assets",           "الأصول الأخرى",          "textarea", ""),
    ],
    "👥 الشبكة الاجتماعية": [
        ("family_members",   "أفراد العائلة",          "textarea", ""),
        ("associates",       "المعارف والمرتبطون",     "textarea", ""),
        ("organizations",    "المنظمات والجماعات",     "textarea", ""),
        ("enemies",          "الخصوم المعروفون",       "textarea", ""),
    ],
    "⚠️ معلومات أمنية": [
        ("criminal_record",  "السجل الجنائي",          "textarea", ""),
        ("threat_level",     "مستوى التهديد",          "choice",   ["منخفض","متوسط","عالٍ","حرج"]),
        ("known_weapons",    "أسلحة معروفة",           "textarea", ""),
        ("travel_history",   "سجل السفر",              "textarea", ""),
        ("financial_links",  "روابط مالية مشبوهة",    "textarea", ""),
    ],
    "📝 ملاحظات المحقق": [
        ("notes",            "ملاحظات عامة",           "textarea", ""),
        ("sources",          "المصادر",                "textarea", ""),
        ("confidence",       "مستوى الثقة بالمعلومات","choice",   ["منخفض","متوسط","عالٍ","مؤكد"]),
        ("case_number",      "رقم القضية",             "text",     ""),
        ("assigned_to",      "المحقق المسؤول",         "text",     ""),
        ("last_updated",     "آخر تحديث",              "date",     ""),
    ],
}

# Flat list of all fields
ALL_FIELDS = []
for group, fields in FIELD_GROUPS.items():
    for f in fields:
        ALL_FIELDS.append(f)

FIELD_NAMES = [f[0] for f in ALL_FIELDS]


@dataclass
class OSINTProfile:
    """A single OSINT target profile."""
    id:           int   = 0
    photo_path:   str   = ""
    created_at:   str   = ""
    updated_at:   str   = ""
    # All fields as a dict
    data:         Dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str:
        return self.data.get(key, "")

    def set(self, key: str, value: str):
        self.data[key] = value

    def display_name(self) -> str:
        return self.data.get("full_name", "") or self.data.get("alias", "") or f"هدف #{self.id}"

    def threat_color(self) -> str:
        level = self.data.get("threat_level", "")
        return {"منخفض": "#3dd68c", "متوسط": "#e8c46a",
                "عالٍ": "#e05577",  "حرج":   "#ff0044"}.get(level, "#3a3a52")


class Database:
    """SQLite database manager for OSINT profiles."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            home = os.path.expanduser("~")
            db_dir = os.path.join(home, ".phantom_osint")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "profiles.db")

        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_path  TEXT    DEFAULT '',
                data_json   TEXT    DEFAULT '{}',
                created_at  TEXT    DEFAULT '',
                updated_at  TEXT    DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS profile_photos (
                profile_id  INTEGER PRIMARY KEY,
                photo_data  BLOB,
                mime_type   TEXT DEFAULT 'image/jpeg'
            )
        """)
        self._conn.commit()

    # ── CRUD ─────────────────────────────────────

    def create_profile(self) -> OSINTProfile:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO profiles (data_json, created_at, updated_at) VALUES (?, ?, ?)",
            ("{}", now, now)
        )
        self._conn.commit()
        return OSINTProfile(id=cur.lastrowid, created_at=now, updated_at=now)

    def save_profile(self, profile: OSINTProfile):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        profile.updated_at = now
        data_json = json.dumps(profile.data, ensure_ascii=False)
        self._conn.execute(
            """UPDATE profiles SET data_json=?, photo_path=?, updated_at=?
               WHERE id=?""",
            (data_json, profile.photo_path, now, profile.id)
        )
        self._conn.commit()

    def load_profile(self, profile_id: int) -> Optional[OSINTProfile]:
        row = self._conn.execute(
            "SELECT * FROM profiles WHERE id=?", (profile_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_profile(row)

    def delete_profile(self, profile_id: int):
        self._conn.execute("DELETE FROM profiles WHERE id=?", (profile_id,))
        self._conn.execute("DELETE FROM profile_photos WHERE profile_id=?", (profile_id,))
        self._conn.commit()

    def list_profiles(self) -> List[OSINTProfile]:
        rows = self._conn.execute(
            "SELECT * FROM profiles ORDER BY updated_at DESC"
        ).fetchall()
        return [self._row_to_profile(r) for r in rows]

    def search_profiles(self, query: str) -> List[OSINTProfile]:
        rows = self._conn.execute(
            "SELECT * FROM profiles WHERE data_json LIKE ? ORDER BY updated_at DESC",
            (f"%{query}%",)
        ).fetchall()
        return [self._row_to_profile(r) for r in rows]

    # ── Photo storage ─────────────────────────────

    def save_photo(self, profile_id: int, photo_bytes: bytes, mime: str = "image/jpeg"):
        self._conn.execute(
            """INSERT OR REPLACE INTO profile_photos (profile_id, photo_data, mime_type)
               VALUES (?, ?, ?)""",
            (profile_id, photo_bytes, mime)
        )
        self._conn.commit()

    def load_photo(self, profile_id: int) -> Optional[bytes]:
        row = self._conn.execute(
            "SELECT photo_data FROM profile_photos WHERE profile_id=?",
            (profile_id,)
        ).fetchone()
        return row["photo_data"] if row else None

    # ── Export ────────────────────────────────────

    def export_profile_json(self, profile: OSINTProfile) -> str:
        return json.dumps({
            "id":         profile.id,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "data":       profile.data,
        }, ensure_ascii=False, indent=2)

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    def _row_to_profile(self, row) -> OSINTProfile:
        try:
            data = json.loads(row["data_json"] or "{}")
        except Exception:
            data = {}
        return OSINTProfile(
            id         = row["id"],
            photo_path = row["photo_path"] or "",
            data       = data,
            created_at = row["created_at"] or "",
            updated_at = row["updated_at"] or "",
        )

    def close(self):
        self._conn.close()
