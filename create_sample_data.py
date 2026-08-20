import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

np.random.seed(42)
random.seed(42)

PROJECT_DIR = __import__('os').path.dirname(__import__('os').path.abspath(__file__))
__import__('os').chdir(PROJECT_DIR)

orgs = ["أمانة الرياض - قطاع الغرب", "بلدية العارض", "بلدية طويق", "بلدية الشفاء", "بلدية بني حنيفة"]
services = ["رخصة بناء جديدة", "ترميم", "إضافة دور", "هدم مبنى", "تعديل مخطط", "رخصة ترميم", "إضافة ملحق", "رخصة بناء"]

stages_done = [
    "تم الاطلاع",
    "إعتماد رئيس البلدية لشهادة اتمام بناء",
    "اعتماد رئيس الجهة",
    "تم تنفيذ التعديل",
    "أعتماد رئيس القسم الفنى للقرار الفنى",
    "اعتماد رئيس القسم الفني شهادة اتمام بناء",
    "منجز",
]
stages_in_progress = [
    "تحويل الى المراقب الفني",
    "تحويل الطلب للمراقب الفني",
    "تحويل الطلب للمراقب الفنى لاصدار شهاده اتمام البناء",
    "تحويل الى رئيس قسم الرخص (المشرف)",
    "تحويل الى المهندس",
    "تحويل الطلب لمدير الإدارة المركزية لرقابة المباني والمنشآت",
    "أعتماد رئيس القسم الفنى للقرار الفنى",
    "تحويل لبلدية",
    "تحويل الطلب للمساح",
    "تحويل الطلب للقسم الفني",
    "ايقاف",
    "تم السداد",
]
stages_returned = [
    "طلب وثائق",
    "ارسلت الى المستفيد",
    "ارجاع طلب تقرير فنى الى رئيس القسم الفنى",
    "ارجاع من المساح",
    "تم تحرير قرار فني",
    "تم تحرير شهادة اتمام بناء",
    "رد الى المهندس",
    "رفض رئيس القسم الفني شهادة اتمام بناء",
    "اصدار تقرير فني للطلب المحول",
]
stages_rejected = ["مرفوض"]
stages_new = ["جديد"]

all_stages = stages_done + stages_in_progress + stages_returned + stages_rejected + stages_new
stage_weights = (
    [8, 5, 5, 3, 5, 5, 4] +
    [15, 10, 8, 5, 5, 4, 3, 3, 3, 2, 2, 2] +
    [12, 8, 5, 4, 4, 3, 3, 2, 2] +
    [2] + [3]
)

owners_names = [f"مالك {i}" for i in range(1, 101)]

records = []
start = datetime(2023, 1, 1)
end = datetime(2026, 7, 19)

for i in range(1, 301):
    d = start + (end - start) * random.random()
    review_delay = random.randint(1, 30)
    review_date = d + timedelta(days=review_delay)
    stage = random.choices(all_stages, weights=stage_weights, k=1)[0]
    if stage in stages_done:
        review_date = d + timedelta(days=random.randint(1, 15))
    elif stage in stages_new:
        review_date = None
    records.append({
        "رقم طلب الخدمة": f"SRV-{i:05d}",
        "السنة": str(d.year),
        "نوع الخدمة": random.choice(services),
        "وصف المرحلة": stage,
        "الجهة": random.choice(orgs),
        "تاريخ الطلب ميلادي": d.strftime("%d/%m/%Y"),
        "تاريخ المراجعة ميلادي": review_date.strftime("%d/%m/%Y") if review_date else "",
        "سنه الرخصة": str(d.year),
        "المالك": random.choice(owners_names),
    })

df = pd.DataFrame(records)
df.to_excel("data.xlsx", index=False, sheet_name="الرخص")
print(f"OK - created data.xlsx with {len(df)} records")
print(f"Stages distribution:")
for s in all_stages:
    count = len(df[df["وصف المرحلة"] == s])
    if count > 0:
        print(f"  {s}: {count}")
