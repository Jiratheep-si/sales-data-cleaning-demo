"""ทำความสะอาดข้อมูลยอดขายและสร้างรายงานคุณภาพข้อมูล ก่อน/หลัง

รัน: python src/clean_data.py
อ่าน:  raw/messy_sales.csv
เขียน: clean/clean_sales.csv, clean/rejected_rows.csv, reports/quality_report.md
"""
import logging
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "messy_sales.csv"
CLEAN = ROOT / "clean" / "clean_sales.csv"
REJECTED = ROOT / "clean" / "rejected_rows.csv"
REPORT = ROOT / "reports" / "quality_report.md"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("clean")

MONTHS_TH = {"ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
             "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12}
CHANNEL_MAP = {"shopee": "Shopee", "lazada": "Lazada", "หน้าร้าน": "หน้าร้าน", "pos": "หน้าร้าน"}
PROVINCE_MAP = {"กรุงเทพฯ": "กรุงเทพมหานคร", "กทม.": "กรุงเทพมหานคร"}
NAME_PREFIX = re.compile(r"^(คุณ|นาย|นาง|น\.ส\.)\s*")
MAX_REASONABLE_PRICE = 10_000


# ---------- ฟังก์ชันแปลงค่า ----------
def parse_date(value):
    """รองรับ ISO, dd/mm/yyyy, dd-mm-yyyy, '14 มี.ค. 2569' (พ.ศ. หรือ ค.ศ.)"""
    if pd.isna(value):
        return pd.NaT
    s = str(value).strip()
    day = month = year = None
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s):
        year, month, day = map(int, m.groups())
    elif m := re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s):
        day, month, year = map(int, m.groups())
    elif m := re.fullmatch(r"(\d{1,2})\s+(\S+)\s+(\d{4})", s):
        day, month_txt, year = int(m[1]), m[2], int(m[3])
        month = MONTHS_TH.get(month_txt)
    if None in (day, month, year):
        return pd.NaT
    if year > 2400:  # พ.ศ. -> ค.ศ.
        year -= 543
    try:
        return pd.Timestamp(year=year, month=month, day=day)
    except ValueError:
        return pd.NaT


def clean_phone(value):
    """แปลงเป็นรูปแบบ 0XXXXXXXXX (10 หลัก) ถ้าไม่ได้ให้เป็นค่าว่าง"""
    if pd.isna(value):
        return pd.NA
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("66") and len(digits) == 11:
        digits = "0" + digits[2:]
    elif len(digits) == 9:
        digits = "0" + digits
    return digits if len(digits) == 10 and digits.startswith("0") else pd.NA


def clean_price(value):
    if pd.isna(value):
        return float("nan")
    s = re.sub(r"[^\d.]", "", str(value))
    return float(s) if s else float("nan")


def clean_name(value):
    if pd.isna(value) or not str(value).strip():
        return pd.NA
    s = re.sub(r"\s+", " ", str(value)).strip()
    return NAME_PREFIX.sub("", s).strip() or pd.NA


# ---------- ตัววัดคุณภาพ ----------
def quality_metrics(df: pd.DataFrame, stage: str) -> dict:
    blank = lambda c: int((df[c].isna() | (df[c].astype(str).str.strip() == "")).sum())
    phone = df["phone"].dropna().astype(str)
    dates = df["order_date"].dropna().astype(str)
    return {
        "phone_bad_format": int((~phone.str.fullmatch(r"0\d{9}")).sum()),
        "dates_not_iso": int((~dates.str.fullmatch(r"\d{4}-\d{2}-\d{2}")).sum()),
        "stage": stage,
        "rows": len(df),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_phone": blank("phone"),
        "missing_name": blank("customer_name"),
        "missing_province": blank("province"),
        "missing_quantity": blank("quantity"),
        "distinct_channels": df["channel"].nunique(),
        "distinct_provinces": df["province"].nunique(),
    }


def clean(df: pd.DataFrame):
    df = df.copy()
    df = df.drop_duplicates()
    df["order_date"] = df["order_date"].map(parse_date)
    df["customer_name"] = df["customer_name"].map(clean_name)
    df["phone"] = df["phone"].map(clean_phone)
    df["channel"] = df["channel"].astype(str).str.strip().str.lower().map(CHANNEL_MAP)
    df["province"] = (df["province"].astype("string").str.strip()
                      .replace(PROVINCE_MAP).replace("", pd.NA))
    df["unit_price"] = df["unit_price"].map(clean_price)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    # แยกแถวที่ใช้ไม่ได้ออกไปตรวจ ไม่ลบทิ้งเงียบๆ
    reasons = pd.Series("", index=df.index)
    reasons[df["order_date"].isna()] += "วันที่ไม่ถูกต้อง; "
    reasons[df["channel"].isna()] += "ไม่รู้จักช่องทางขาย; "
    reasons[df["quantity"].isna() | (df["quantity"] <= 0)] += "จำนวนไม่ถูกต้อง; "
    reasons[df["unit_price"].isna() | (df["unit_price"] <= 0)
            | (df["unit_price"] > MAX_REASONABLE_PRICE)] += "ราคาผิดปกติ; "
    bad = reasons != ""
    rejected = df[bad].assign(reject_reason=reasons[bad])
    good = df[~bad].copy()

    good["quantity"] = good["quantity"].astype(int)
    good["total"] = good["quantity"] * good["unit_price"]
    good = good.sort_values("order_date").reset_index(drop=True)
    return good, rejected


def write_report(before: dict, after: dict, n_rejected: int, reasons: pd.Series) -> None:
    rows = [
        ("จำนวนแถว", "rows"),
        ("แถวซ้ำ", "duplicate_rows"),
        ("วันที่ไม่อยู่ในรูปแบบ YYYY-MM-DD (ปนทั้ง พ.ศ./ค.ศ.)", "dates_not_iso"),
        ("เบอร์โทรที่ฟอร์แมตไม่เป็นมาตรฐาน 0XXXXXXXXX", "phone_bad_format"),
        ("เบอร์โทรว่าง/ใช้ไม่ได้", "missing_phone"),
        ("ชื่อลูกค้าว่าง", "missing_name"),
        ("จังหวัดว่าง", "missing_province"),
        ("จำนวนสินค้าว่าง", "missing_quantity"),
        ("ชื่อช่องทางขายที่ไม่ซ้ำ (ยิ่งน้อยยิ่งสะอาด)", "distinct_channels"),
        ("ชื่อจังหวัดที่ไม่ซ้ำ", "distinct_provinces"),
    ]
    lines = ["# รายงานคุณภาพข้อมูล (Before / After)", "",
             "| ตัวชี้วัด | ก่อน | หลัง |", "|---|---:|---:|"]
    for label, key in rows:
        lines.append(f"| {label} | {before[key]:,} | {after[key]:,} |")
    lines += ["", f"แถวที่ถูกแยกไปตรวจสอบ (ไม่ลบทิ้ง): **{n_rejected:,}** แถว "
              "-> `clean/rejected_rows.csv`", ""]
    if n_rejected:
        lines += ["สาเหตุที่แยกออก:", ""]
        for reason, cnt in reasons.value_counts().items():
            lines.append(f"- {reason.strip('; ')}: {cnt:,} แถว")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    raw = pd.read_csv(RAW, dtype=str, keep_default_na=False, na_values=[""])
    log.info("อ่านข้อมูลดิบ %s แถว", f"{len(raw):,}")
    before = quality_metrics(raw, "before")

    good, rejected = clean(raw)
    # หลังทำความสะอาด: นับ 'ว่าง' จากค่า NA จริง
    after = quality_metrics(good.astype({"quantity": "object"}), "after")
    log.info("แถวที่ใช้ได้ %s | แยกไปตรวจ %s", f"{len(good):,}", f"{len(rejected):,}")

    CLEAN.parent.mkdir(exist_ok=True)
    good.to_csv(CLEAN, index=False, encoding="utf-8-sig")
    rejected.to_csv(REJECTED, index=False, encoding="utf-8-sig")
    write_report(before, after, len(rejected),
                 rejected["reject_reason"] if len(rejected) else pd.Series(dtype=str))
    log.info("เขียนรายงานที่ %s", REPORT)


if __name__ == "__main__":
    main()
