"""สร้างข้อมูลยอดขายร้านค้าออนไลน์สมมติที่ "รก" โดยตั้งใจ

ข้อมูลทั้งหมดเป็นข้อมูลจำลอง ไม่มีข้อมูลจริงของใคร
รัน: python src/generate_messy_data.py
ผลลัพธ์: raw/messy_sales.csv
"""
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 42
N_ORDERS = 1500
random.seed(SEED)

FIRST = ["สมชาย", "สมหญิง", "วิชัย", "ปราณี", "อนันต์", "กนกวรรณ", "ธีรพงษ์",
         "นภัสสร", "พิมพ์ชนก", "ณัฐวุฒิ", "สุภาพร", "ประเสริฐ", "ชลธิชา", "รัตนา"]
LAST = ["ใจดี", "รักษา", "แสงทอง", "ศรีสุข", "มั่นคง", "วงศ์ไทย", "เจริญพร",
        "บุญมา", "สุขสวัสดิ์", "ทองดี"]
PREFIX = ["", "", "", "คุณ", "นาย", "นาง", "น.ส."]
PRODUCTS = {
    "เสื้อยืดคอกลม": 290, "กางเกงยีนส์": 890, "กระเป๋าผ้า": 350,
    "รองเท้าผ้าใบ": 1290, "หมวกแก๊ป": 250, "เข็มขัดหนัง": 490,
}
CHANNELS = ["Shopee", "shopee", "SHOPEE", "Lazada", "lazada", "LAZADA",
            "หน้าร้าน", "POS", "หน้าร้าน "]
STATUS = ["สำเร็จ", "สำเร็จ", "สำเร็จ", "ยกเลิก", "รอจัดส่ง", "ส่งแล้ว"]
PROVINCES = ["กรุงเทพมหานคร", "กรุงเทพฯ", "กทม.", "เชียงใหม่", "ขอนแก่น",
             "ชลบุรี", "ภูเก็ต", "นนทบุรี", "นครราชสีมา", "สงขลา"]
MONTHS_TH = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def messy_date(d: date) -> str:
    fmt = random.choice(["iso", "dmy", "dmy_be", "th_text", "dash_be"])
    if fmt == "iso":
        return d.strftime("%Y-%m-%d")
    if fmt == "dmy":
        return d.strftime("%d/%m/%Y")
    if fmt == "dmy_be":
        return f"{d.day:02d}/{d.month:02d}/{d.year + 543}"
    if fmt == "th_text":
        return f"{d.day} {MONTHS_TH[d.month - 1]} {d.year + 543}"
    return f"{d.day:02d}-{d.month:02d}-{d.year + 543}"


def messy_phone(digits: str) -> str:
    fmt = random.choice(["plain", "dash", "space", "intl", "intl_space", "no_zero"])
    a, b, c = digits[:3], digits[3:6], digits[6:]
    if fmt == "plain":
        return digits
    if fmt == "dash":
        return f"{a}-{b}-{c}"
    if fmt == "space":
        return f"{a} {b} {c}"
    if fmt == "intl":
        return "+66" + digits[1:]
    if fmt == "intl_space":
        return f"+66 {digits[1:3]} {b} {c}"
    return digits[1:]  # ขาดเลข 0 นำหน้า


def messy_price(p: int) -> str:
    fmt = random.choice(["plain", "comma", "baht_sym", "baht_txt", "decimal"])
    if fmt == "plain":
        return str(p)
    if fmt == "comma":
        return f"{p:,}"
    if fmt == "baht_sym":
        return f"฿{p:,}"
    if fmt == "baht_txt":
        return f"{p} บาท"
    return f"{p}.00"


def messy_name(first: str, last: str) -> str:
    name = f"{random.choice(PREFIX)}{first} {last}".strip()
    style = random.choice(["ok", "ok", "ok", "spaces", "extra_inner"])
    if style == "spaces":
        return f"  {name}  "
    if style == "extra_inner":
        return name.replace(" ", "   ")
    return name


def main() -> None:
    start = date(2026, 1, 1)
    customers = []
    for _ in range(300):
        customers.append((
            random.choice(FIRST), random.choice(LAST),
            "0" + random.choice("689") + "".join(random.choices("0123456789", k=8)),
        ))

    rows = []
    for i in range(1, N_ORDERS + 1):
        first, last, phone = random.choice(customers)
        product = random.choice(list(PRODUCTS))
        d = start + timedelta(days=random.randint(0, 180))
        rows.append({
            "order_id": f"ORD{i:05d}",
            "order_date": messy_date(d),
            "customer_name": messy_name(first, last),
            "phone": messy_phone(phone),
            "channel": random.choice(CHANNELS),
            "product": product,
            "quantity": random.choices([1, 2, 3, 4, 5], weights=[60, 20, 10, 6, 4])[0],
            "unit_price": messy_price(PRODUCTS[product]),
            "status": random.choice(STATUS),
            "province": random.choice(PROVINCES),
        })

    df = pd.DataFrame(rows)

    # ใส่ปัญหาเพิ่ม: ค่าว่าง, ค่าผิดปกติ
    df["quantity"] = df["quantity"].astype("object")
    for seed, (col, frac) in enumerate([("phone", 0.04), ("province", 0.03),
                                        ("customer_name", 0.02), ("quantity", 0.02)], start=10):
        idx = df.sample(frac=frac, random_state=seed).index  # seed ต่างกัน -> สุ่มคนละแถว
        df[col] = df[col].astype("object")
        df.loc[idx, col] = [random.choice([None, ""]) for _ in idx]
    for i in df.sample(6, random_state=1).index:
        df.at[i, "quantity"] = -1  # จำนวนติดลบ
    for i in df.sample(4, random_state=2).index:
        df.at[i, "unit_price"] = "999999"  # ราคาผิดปกติ

    # แถวซ้ำ (ส่งออกซ้ำจากระบบ) และ order_id ซ้ำที่ข้อมูลต่างกันเล็กน้อย
    dups = df.sample(80, random_state=3)
    df = pd.concat([df, dups], ignore_index=True)
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

    out = Path(__file__).resolve().parent.parent / "raw" / "messy_sales.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"สร้างข้อมูลรก {len(df):,} แถว -> {out}")


if __name__ == "__main__":
    main()
