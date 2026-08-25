import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

st.set_page_config(page_title="مؤشر أداء رخص البناء", page_icon="🏗️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@300;400;500;600;700;800&display=swap');
    * { font-family: 'Noto Sans Arabic', sans-serif !important; }
    .main { direction: rtl; }
    .stApp { direction: rtl; background: #f0f2f6; }
    .block-container { padding: 0.5rem 1rem !important; max-width: 100% !important; }
    div[data-testid="stSidebar"] { direction: rtl; background: linear-gradient(180deg, #1a3a2a 0%, #0d1f15 100%); }
    div[data-testid="stSidebar"] .stMarkdown { color: #e0e0e0; }
    div[data-testid="stSidebar"] label { color: #c0d0c0 !important; }
    div[data-testid="stSidebar"] .stMultiSelect label { color: #c0d0c0 !important; }

    .header-bar { background: linear-gradient(135deg, #0d3320 0%, #1a5c3a 50%, #0d3320 100%); padding: 14px 24px; border-radius: 12px; color: white; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(13,51,32,0.3); }
    .header-bar h1 { font-size: 20px; font-weight: 800; margin: 0; letter-spacing: 0.5px; }
    .header-bar .sub { font-size: 11px; opacity: 0.85; margin: 2px 0 0 0; font-weight: 300; }
    .header-bar .badge { background: rgba(255,255,255,0.15); padding: 3px 10px; border-radius: 20px; font-size: 10px; font-weight: 600; }

    .kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 12px; }
    .kpi { background: white; border-radius: 10px; padding: 12px 10px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e8ecf0; position: relative; overflow: hidden; transition: transform 0.2s, box-shadow 0.2s; }
    .kpi:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
    .kpi-val { font-size: 26px; font-weight: 800; direction: ltr; display: inline-block; }
    .kpi-lbl { font-size: 11px; color: #64748b; margin-top: 2px; font-weight: 600; }
    .kpi-sub { font-size: 9px; color: #94a3b8; margin-top: 1px; }
    .kpi-bar { height: 3px; border-radius: 0 0 10px 10px; position: absolute; bottom: 0; left: 0; right: 0; }
    .k-total .kpi-val { color: #1e293b; } .k-total .kpi-bar { background: #64748b; }
    .k-done .kpi-val { color: #15803d; } .k-done .kpi-bar { background: linear-gradient(90deg, #22c55e, #15803d); }
    .k-ret .kpi-val { color: #2563eb; } .k-ret .kpi-bar { background: linear-gradient(90deg, #60a5fa, #2563eb); }
    .k-prog .kpi-val { color: #d97706; } .k-prog .kpi-bar { background: linear-gradient(90deg, #fbbf24, #d97706); }
    .k-rej .kpi-val { color: #dc2626; } .k-rej .kpi-bar { background: linear-gradient(90deg, #f87171, #dc2626); }
    .k-new .kpi-val { color: #7c3aed; } .k-new .kpi-bar { background: linear-gradient(90deg, #a78bfa, #7c3aed); }
    .k-stop .kpi-val { color: #9333ea; } .k-stop .kpi-bar { background: linear-gradient(90deg, #c084fc, #9333ea); }

    .box { background: white; border-radius: 10px; padding: 12px; box-shadow: 0 1px 6px rgba(0,0,0,0.04); border: 1px solid #e8ecf0; margin-bottom: 8px; }
    .box-title { font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 2px solid #f1f5f9; }
    .section-title { font-size: 15px; font-weight: 700; color: #0d3320; margin: 12px 0 8px 0; padding-right: 8px; border-right: 4px solid #15803d; padding-left: 8px; }

    .btn-filter { display: inline-block; padding: 5px 14px; border-radius: 8px; font-size: 11px; font-weight: 600; cursor: pointer; border: 1px solid #e2e8f0; background: #f8fafc; color: #475569; transition: all 0.2s; margin: 2px; }
    .btn-filter:hover { background: #e2e8f0; }
    .btn-active { background: #0d3320 !important; color: white !important; border-color: #0d3320 !important; }

    .metric-row { display: flex; gap: 12px; margin-bottom: 10px; }
    .metric-card { flex: 1; background: white; border-radius: 10px; padding: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e8ecf0; }
    .metric-val { font-size: 20px; font-weight: 800; color: #15803d; direction: ltr; }
    .metric-lbl { font-size: 10px; color: #64748b; font-weight: 600; }

    .footer { text-align: center; color: #94a3b8; font-size: 10px; padding: 10px 0 4px 0; border-top: 1px solid #e8ecf0; margin-top: 10px; }

    button[data-testid="baseButton-secondary"] { background: #15803d; color: white; border: none; font-size: 12px; }
    button[data-testid="baseButton-secondary"]:hover { background: #166534; }

    /* زر إظهار الفلتر */
    .show-filter-btn { position: fixed; top: 10px; right: 10px; background: #15803d; color: white; border: none; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 700; cursor: pointer; z-index: 999; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
    .show-filter-btn:hover { background: #166534; }

    .filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
    .filter-toggle { background: #0d3320; color: white; border: none; border-radius: 8px; padding: 6px 16px 6px 12px; font-size: 13px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; transition: all 0.2s; }
    .filter-toggle:hover { background: #1a5c3a; }
    button[kind="primary"] { background: #0d3320 !important; color: white !important; border: none !important; font-size: 13px !important; font-weight: 700 !important; border-radius: 8px !important; padding: 6px 18px !important; gap: 6px !important; }
    button[kind="primary"]:hover { background: #1a5c3a !important; }
</style>
""", unsafe_allow_html=True)

# ======================== تهيئة الحالة =============================
if "filter_stage" not in st.session_state:
    st.session_state.filter_stage = "الكل"
if "show_filters" not in st.session_state:
    st.session_state.show_filters = False
if "data_source" not in st.session_state:
    st.session_state.data_source = "none"

# ======================== دوال معالجة البيانات ======================
def process_data(df):
    if df is None:
        return None
    cols = list(df.columns)
    col_map = {
        "طلب الخدمة": "رقم طلب الخدمة", "نوع الخدمة": "نوع الخدمة",
        "الجهة": "الجهة", "الجهه": "الجهة",
        "السنة": "السنة", "سنه الرخصة": "سنه الرخصة",
        "المالك": "المالك", "الملالك": "المالك",
    }
    col_rename = {}
    for c in cols:
        cs = c.strip()
        if cs in col_map:
            col_rename[c] = col_map[cs]
        elif "ميلادي" in cs and "تاريخ" in cs and "طلب" in cs:
            col_rename[c] = "تاريخ الطلب ميلادي"
        elif "ميلادي" in cs and "تاريخ" in cs and "مراجعة" in cs:
            col_rename[c] = "تاريخ المراجعة ميلادي"
    df.rename(columns=col_rename, inplace=True)

    for dcol in ["تاريخ الطلب ميلادي", "تاريخ المراجعة ميلادي"]:
        if dcol in df.columns:
            df[dcol] = df[dcol].astype(str)
            df[dcol] = pd.to_datetime(df[dcol], format="%d/%m/%Y", errors="coerce")
            if df[dcol].isna().all():
                df[dcol] = pd.to_datetime(df[dcol].astype(str).str.strip(), errors="coerce")

    if "تاريخ الطلب ميلادي" in df.columns:
        df["الشهر"] = df["تاريخ الطلب ميلادي"].dt.month
        df["اسم الشهر"] = df["تاريخ الطلب ميلادي"].dt.strftime("%Y-%m")
        df["اليوم"] = df["تاريخ الطلب ميلادي"].dt.day_name()
        df["رقم الشهر"] = df["تاريخ الطلب ميلادي"].dt.month
        if "تاريخ المراجعة ميلادي" in df.columns:
            df["مدة الإنجاز (أيام)"] = (df["تاريخ المراجعة ميلادي"] - df["تاريخ الطلب ميلادي"]).dt.days
            df["مدة الإنجاز (أيام)"] = df["مدة الإنجاز (أيام)"].clip(lower=0)

    if "السنة" not in df.columns and "سنه الرخصة" in df.columns:
        df["السنة"] = df["سنه الرخصة"]
    if "السنة" in df.columns:
        df["السنة"] = df["السنة"].astype(str)

    return df

# ======================== تحميل الملف الافتراضي ====================
if st.session_state.data_source == "none":
    if os.path.exists("data.xlsx"):
        tmp = process_data(pd.read_excel("data.xlsx"))
        if tmp is not None:
            st.session_state["df"] = tmp
            st.session_state.data_source = "default"
    elif os.path.exists("data.xls"):
        try:
            tmp = process_data(pd.read_html("data.xls", encoding="utf-8")[0])
            if tmp is not None:
                st.session_state["df"] = tmp
                st.session_state.data_source = "default"
        except:
            try:
                tmp = process_data(pd.read_html("data.xls", encoding="cp1256")[0])
                if tmp is not None:
                    st.session_state["df"] = tmp
                    st.session_state.data_source = "default"
            except:
                pass

# ======================== اختيار مصدر البيانات =====================
if "df" not in st.session_state:
    st.warning("⚠️ لا يوجد ملف بيانات افتراضي في المجلد")
    st.markdown("## اختر طريقة إدخال البيانات")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 1. سحب من البوابة")
        st.write("ضع ملف data.xlsx أو data.xls في مجلد المشروع ثم:")
        if st.button("🔄 إعادة تحميل الملف الافتراضي", use_container_width=True):
            if os.path.exists("data.xlsx"):
                tmp = process_data(pd.read_excel("data.xlsx"))
                if tmp is not None:
                    st.session_state["df"] = tmp
                    st.session_state.data_source = "default"
                    st.rerun()
            if os.path.exists("data.xls"):
                try:
                    tmp = process_data(pd.read_html("data.xls", encoding="utf-8")[0])
                    if tmp is not None:
                        st.session_state["df"] = tmp
                        st.session_state.data_source = "default"
                        st.rerun()
                except:
                    try:
                        tmp = process_data(pd.read_html("data.xls", encoding="cp1256")[0])
                        if tmp is not None:
                            st.session_state["df"] = tmp
                            st.session_state.data_source = "default"
                            st.rerun()
                    except:
                        pass
            st.error("لم يتم العثور على ملف بيانات في المجلد")
    with col2:
        st.markdown("### 2. رفع ملف من جهازك")
        st.write("إذا تعذر السحب من البوابة، ارفع الملف Excel يدوياً:")
        uploaded = st.file_uploader("اختر ملف Excel", type=["xlsx", "xls", "csv"], label_visibility="collapsed")
        if uploaded is not None:
            try:
                if uploaded.name.endswith(".csv"):
                    df_uploaded = pd.read_csv(uploaded)
                else:
                    df_uploaded = pd.read_excel(uploaded)
                df_uploaded = process_data(df_uploaded)
                if df_uploaded is not None and "وصف المرحلة" in df_uploaded.columns:
                    st.success(f"✅ تم رفع {len(df_uploaded)} سجل من {uploaded.name}")
                    st.session_state["df"] = df_uploaded
                    st.session_state.data_source = "uploaded"
                    st.rerun()
                else:
                    st.error("تعذرت معالجة الملف. تأكد أنه يحتوي على عمود 'وصف المرحلة'.")
            except Exception as e:
                st.error(f"خطأ في قراءة الملف: {e}")
    st.stop()

df = st.session_state["df"]

stages_done = [
    "تم الاطلاع", "إعتماد رئيس البلدية لشهادة اتمام بناء", "اعتماد رئيس الجهة",
    "تم تنفيذ التعديل", "منجز",
    "مرفوض", "ايقاف",
    "طلب تعديل من المستفيد",
]
stages_returned = [
    "طلب وثائق", "ارسلت الى المستفيد", "ارجاع طلب",
    "رد الى المهندس", "رفض شهادة اتمام بناء",
]
stages_in_progress = [
    "تحويل الى المراقب الفني", "تحويل الى المهندس",
    "تحويل لبلدية", "تم السداد",
    "إصدار قرار مساحي", "تجزئة ودمج", "تحديث صك",
    "قرار مساحي", "إصدار شهادات اشغال",
    "ارجاع طلب تقرير فنى الى رئيس القسم الفنى",
    "ارجاع من المساح",     "اصدار تقرير فني للطلب المحول", "إصدار تقرير فني للطلب المحول",
    "تحويل الطلب للقسم الفني",     "تحويل الطلب للمراقب الفني",
    "تحويل الطلب للمراقب الفنى لاصدار شهاده اتمام البناء",
    "تحويل الطلب لمدير الإدارة المركزية لرقابة المباني والمنشآت",
    "تحويل الى رئيس قسم الرخص (المشرف)", "استلام معد المحضر الفنى",
]
stages_stopped = []
stages_rejected = []
stages_new = ["جديد"]

def classify(stage):
    if pd.isna(stage) or str(stage).strip() == "":
        return "غير محدد"
    s = str(stage).strip()
    if s in stages_done: return "منجز"
    if s in stages_returned: return "معاد للمستفيد"
    if s in stages_new: return "جديد"
    if s in stages_in_progress: return "تحت الإجراء"
    return "غير محدد"

df["تصنيف"] = df["وصف المرحلة"].apply(classify)

df_f = df.copy()

today = datetime.now()
if "تاريخ الطلب ميلادي" in df.columns and not df["تاريخ الطلب ميلادي"].isna().all():
    today = df["تاريخ الطلب ميلادي"].max()
    if pd.isna(today):
        today = datetime.now()
    min_date = df["تاريخ الطلب ميلادي"].min()
    max_date = df["تاريخ الطلب ميلادي"].max()
else:
    min_date = datetime(2023, 1, 1)
    max_date = datetime.now()

arrow_label = "◀" if st.session_state.show_filters else "▶"
toggle_label = f"{arrow_label} {('إخفاء' if st.session_state.show_filters else 'إظهار')} الفلتر"
r1, r2, r3 = st.columns([1, 1, 10])
with r1:
    if st.button(toggle_label, key="filter-btn", type="primary"):
        st.session_state.show_filters = not st.session_state.show_filters
        st.rerun()
with r2:
    if st.button("🔄 تحديث", type="secondary"):
        if os.path.exists("data.xlsx"):
            tmp = process_data(pd.read_excel("data.xlsx"))
            if tmp is not None:
                st.session_state["df"] = tmp
                st.session_state.data_source = "default"
                st.success("✅ تم تحديث البيانات")
                st.rerun()
        elif os.path.exists("data.xls"):
            try:
                tmp = process_data(pd.read_html("data.xls", encoding="utf-8")[0])
                if tmp is not None:
                    st.session_state["df"] = tmp
                    st.session_state.data_source = "default"
                    st.success("✅ تم تحديث البيانات")
                    st.rerun()
            except:
                pass
        st.error("⚠️ لا يوجد ملف بيانات في المجلد")

if st.session_state.show_filters:
    st.markdown("<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:10px;margin-bottom:8px;'>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("##### 📅 الفترة الزمنية")
        filter_mode = st.radio("الفترة", ["خلال اليوم", "خلال الأسبوع", "خلال الشهر", "خلال الربع", "خلال السنة", "تاريخ مخصص"], index=3, label_visibility="collapsed")

        if filter_mode == "تاريخ مخصص":
            dr = st.date_input("اختر الفترة", [min_date.date(), max_date.date()], min_value=min_date.date(), max_value=max_date.date(), label_visibility="collapsed")
            sf = datetime.combine(dr[0], datetime.min.time()) if len(dr) >= 1 else min_date
            ef = datetime.combine(dr[-1], datetime.max.time()) if len(dr) >= 2 else max_date
        elif filter_mode == "خلال اليوم":
            sf = today.replace(hour=0, minute=0, second=0, microsecond=0)
            ef = today.replace(hour=23, minute=59, second=59)
        elif filter_mode == "خلال الأسبوع":
            sf = (today - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            ef = today.replace(hour=23, minute=59, second=59)
        elif filter_mode == "خلال الشهر":
            sf = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            ef = today.replace(hour=23, minute=59, second=59)
        elif filter_mode == "خلال الربع":
            q = (today.month - 1) // 3
            sf = datetime(today.year, q * 3 + 1, 1)
            ef = today.replace(hour=23, minute=59, second=59)
        elif filter_mode == "خلال السنة":
            sf = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            ef = today.replace(hour=23, minute=59, second=59)

        st.markdown(f"<div style='background:#f0f4f8;padding:4px 8px;border-radius:6px;font-size:11px;text-align:center;'>{sf.date()} ← {ef.date()}</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("##### 🔍 تصفية حسب")
        if "نوع الخدمة" in df.columns:
            flt_خدمة = st.multiselect("نوع الخدمة", sorted(df["نوع الخدمة"].dropna().unique()), default=None, placeholder="الكل")
        else:
            flt_خدمة = []

    with c3:
        st.markdown("##### &nbsp;")
        if "الجهة" in df.columns:
            flt_جهة = st.multiselect("الجهة", sorted(df["الجهة"].dropna().unique()), default=None, placeholder="الكل")
        else:
            flt_جهة = []
        if "السنة" in df.columns:
            flt_سنة = st.multiselect("السنة", sorted(df["السنة"].dropna().unique()), default=None, placeholder="الكل")
        else:
            flt_سنة = []
    st.markdown("</div>", unsafe_allow_html=True)
else:
    sf = min_date
    ef = max_date
    flt_خدمة = []
    flt_جهة = []
    flt_سنة = []

if "تاريخ الطلب ميلادي" in df.columns and not df["تاريخ الطلب ميلادي"].isna().all():
    df_f = df[(df["تاريخ الطلب ميلادي"] >= sf) & (df["تاريخ الطلب ميلادي"] <= ef)].copy()
else:
    df_f = df.copy()

if flt_خدمة: df_f = df_f[df_f["نوع الخدمة"].isin(flt_خدمة)]
if flt_جهة: df_f = df_f[df_f["الجهة"].isin(flt_جهة)]
if flt_سنة: df_f = df_f[df_f["السنة"].isin(flt_سنة)]

total = len(df_f)
done = (df_f["تصنيف"] == "منجز").sum()
returned = (df_f["تصنيف"] == "معاد للمستفيد").sum()
in_prog = (df_f["تصنيف"] == "تحت الإجراء").sum()
new = (df_f["تصنيف"] == "جديد").sum()
unspecified = (df_f["تصنيف"] == "غير محدد").sum()

total_done = done + returned
done_pct = round(done / total * 100, 1) if total else 0
ret_pct = round(returned / total * 100, 1) if total else 0
total_done_pct = round(total_done / total * 100, 1) if total else 0
in_pct = round(in_prog / total * 100, 1) if total else 0
new_pct = round(new / total * 100, 1) if total else 0

avg_duration = 0
if "مدة الإنجاز (أيام)" in df_f.columns:
    total_duration = df_f["مدة الإنجاز (أيام)"].dropna().sum()
    avg_duration = int(total_duration / total) if total > 0 else 0

st.markdown(f"""
<div class="header-bar">
    <div>
        <h1>🏗️ مؤشر أداء رخص البناء</h1>
        <p class="sub">أمانة منطقة الرياض — قطاع الغرب | آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {'📁 مستند مرفوع' if st.session_state.data_source == 'uploaded' else '📀 ملف افتراضي'} | إجمالي البيانات: {len(df):,} سجل</p>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
        <span class="badge">{'📤 مرفوع' if st.session_state.data_source == 'uploaded' else '📀 افتراضي'}</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""<div class="kpi-grid">
    <div class="kpi k-total"><div class="kpi-val">{total:,}</div><div class="kpi-lbl">📋 إجمالي الطلبات</div><div class="kpi-sub">في الفترة المحددة</div><div class="kpi-bar"></div></div>
    <div class="kpi k-done"><div class="kpi-val">{total_done:,}</div><div class="kpi-lbl">✅ منجز</div><div class="kpi-sub">{total_done_pct}% من الإجمالي (شامل معاد للمستفيد)</div><div class="kpi-bar"></div></div>
    <div class="kpi k-ret"><div class="kpi-val">{returned:,}</div><div class="kpi-lbl">🔄 معاد للمستفيد</div><div class="kpi-sub">{ret_pct}% من الإجمالي (محسوب مع منجز)</div><div class="kpi-bar"></div></div>
    <div class="kpi k-prog"><div class="kpi-val">{in_prog:,}</div><div class="kpi-lbl">⚙️ تحت الإجراء</div><div class="kpi-sub">{in_pct}% من الإجمالي</div><div class="kpi-bar"></div></div>
    <div class="kpi k-new"><div class="kpi-val">{new:,}</div><div class="kpi-lbl">🆕 جديد</div><div class="kpi-sub">{new_pct}% من الإجمالي</div><div class="kpi-bar"></div></div>
</div>""", unsafe_allow_html=True)

st.markdown(f"""<div class="metric-row">
    <div class="metric-card"><div class="metric-val">{avg_duration} يوم</div><div class="metric-lbl">⏱️ متوسط مدة الإنجاز</div></div>
    <div class="metric-card"><div class="metric-val">{total_done_pct}%</div><div class="metric-lbl">📈 نسبة الإنجاز (شامل معاد للمستفيد)</div></div>
    <div class="metric-card"><div class="metric-val">{in_pct}%</div><div class="metric-lbl">⚙️ نسبة تحت الإجراء</div></div>
    <div class="metric-card"><div class="metric-val">{len(df_f[df_f['تاريخ الطلب ميلادي'].dt.year == today.year]) if 'تاريخ الطلب ميلادي' in df_f.columns and not df_f['تاريخ الطلب ميلادي'].isna().all() else 0:,}</div><div class="metric-lbl">📅 طلبات سنة {today.year}</div></div>
</div>""", unsafe_allow_html=True)

filter_labels = {"الكل": "الكل", "منجز": "✅ منجز", "معاد للمستفيد": "🔄 معاد للمستفيد", "تحت الإجراء": "⚙️ تحت الإجراء", "جديد": "🆕 جديد", "غير محدد": "❓ غير محدد"}
filter_cols = st.columns(6)
filter_options = ["الكل", "منجز", "معاد للمستفيد", "تحت الإجراء", "جديد", "غير محدد"]
filter_counts = [total, done, returned, in_prog, new, unspecified]

for i, (opt, cnt) in enumerate(zip(filter_options, filter_counts)):
    with filter_cols[i]:
        label = f"{filter_labels[opt]} ({cnt:,})"
        is_active = st.session_state.filter_stage == opt
        if st.button(label, key=f"btn_{opt}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.filter_stage = opt
            st.rerun()

if st.session_state.filter_stage != "الكل":
    df_f = df_f[df_f["تصنيف"] == st.session_state.filter_stage]

st.markdown(f'<div class="section-title">📊 عرض: {filter_labels.get(st.session_state.filter_stage, st.session_state.filter_stage)} — {len(df_f):,} سجل</div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">📈 التوزيعات والاتجاهات</div>', unsafe_allow_html=True)
r1, r2, r3 = st.columns(3)
with r1:
    st.markdown('<div class="box"><div class="box-title">🍩 توزيع الطلبات حسب التصنيف</div>', unsafe_allow_html=True)
    pie_data = df["تصنيف"].value_counts().reset_index()
    pie_data.columns = ["الحالة", "العدد"]
    color_map_pie = {"منجز": "#15803d", "معاد للمستفيد": "#2563eb", "تحت الإجراء": "#d97706", "جديد": "#7c3aed", "غير محدد": "#94a3b8"}
    fig = px.pie(pie_data, names="الحالة", values="العدد", hole=0.55, color="الحالة", color_discrete_map=color_map_pie)
    fig.update_layout(height=220, margin=dict(l=5, r=5, t=10, b=5), showlegend=True, legend=dict(font=dict(size=9), orientation="h", y=-0.1))
    fig.update_traces(textposition='inside', textinfo='percent', textfont_size=10, marker=dict(line=dict(color='white', width=2)))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with r2:
    st.markdown('<div class="box"><div class="box-title">📊 توزيع الطلبات حسب نوع الخدمة</div>', unsafe_allow_html=True)
    if "نوع الخدمة" in df_f.columns:
        svc = df_f["نوع الخدمة"].value_counts().reset_index()
        svc.columns = ["الخدمة", "العدد"]
        fig = px.bar(svc, x="الخدمة", y="العدد", color="العدد", color_continuous_scale=["#bbf7d0", "#15803d"])
        fig.update_layout(height=220, margin=dict(l=5, r=5, t=10, b=40), showlegend=False, xaxis=dict(tickfont=dict(size=9), tickangle=-30), yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("بيانات نوع الخدمة غير متوفرة")
    st.markdown('</div>', unsafe_allow_html=True)

with r3:
    st.markdown('<div class="box"><div class="box-title">🏛️ توزيع الطلبات حسب الجهة</div>', unsafe_allow_html=True)
    if "الجهة" in df_f.columns:
        ent = df_f["الجهة"].value_counts().reset_index()
        ent.columns = ["الجهة", "العدد"]
        fig = px.bar(ent, x="العدد", y="الجهة", orientation="h", color="العدد", color_continuous_scale=["#bbf7d0", "#0d3320"])
        fig.update_layout(height=220, margin=dict(l=5, r=5, t=10, b=5), showlegend=False, yaxis=dict(tickfont=dict(size=9)), xaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("بيانات الجهة غير متوفرة")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">📈 الاتجاهات الزمنية</div>', unsafe_allow_html=True)
r4, r5, r6 = st.columns(3)

with r4:
    st.markdown('<div class="box"><div class="box-title">📈 الاتجاه الشهري للطلبات</div>', unsafe_allow_html=True)
    if "تاريخ الطلب ميلادي" in df_f.columns and not df_f["تاريخ الطلب ميلادي"].isna().all():
        monthly = df_f.set_index("تاريخ الطلب ميلادي").resample("ME").size().reset_index()
        monthly.columns = ["الشهر", "العدد"]
        monthly["المتوسط"] = monthly["العدد"].rolling(window=3, min_periods=1).mean().round(0)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=monthly["الشهر"], y=monthly["العدد"], name="عدد الطلبات", marker_color="#86efac", opacity=0.7), secondary_y=False)
        fig.add_trace(go.Scatter(x=monthly["الشهر"], y=monthly["المتوسط"], name="المتوسط المتحرك", line=dict(color="#15803d", width=2, dash="dot"), mode="lines"), secondary_y=True)
        fig.update_layout(height=210, margin=dict(l=5, r=5, t=10, b=5), showlegend=True, legend=dict(font=dict(size=8), orientation="h", y=-0.15), xaxis=dict(tickfont=dict(size=8)), yaxis=dict(tickfont=dict(size=8)), yaxis2=dict(tickfont=dict(size=8)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("بيانات التاريخ غير متوفرة")
    st.markdown('</div>', unsafe_allow_html=True)

with r5:
    st.markdown('<div class="box"><div class="box-title">📊 مقارنة التصنيفات حسب السنة</div>', unsafe_allow_html=True)
    if "السنة" in df_f.columns:
        cat = df_f.groupby(["السنة", "تصنيف"]).size().reset_index(name="العدد")
        fig = px.bar(cat, x="السنة", y="العدد", color="تصنيف", barmode="stack",
                     color_discrete_map={"منجز": "#15803d", "معاد للمستفيد": "#2563eb", "تحت الإجراء": "#d97706", "جديد": "#7c3aed", "غير محدد": "#94a3b8"})
        fig.update_layout(height=210, margin=dict(l=5, r=5, t=10, b=5), legend=dict(font=dict(size=8), orientation="h", y=-0.15), xaxis=dict(tickfont=dict(size=9)), yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("بيانات السنة غير متوفرة")
    st.markdown('</div>', unsafe_allow_html=True)

with r6:
    st.markdown('<div class="box"><div class="box-title">⏱️ متوسط مدة الإنجاز حسب نوع الخدمة</div>', unsafe_allow_html=True)
    if "مدة الإنجاز (أيام)" in df_f.columns and "نوع الخدمة" in df_f.columns:
        dur_data = df_f[df_f["تصنيف"] == "منجز"].groupby("نوع الخدمة")["مدة الإنجاز (أيام)"].mean().dropna().reset_index()
        dur_data.columns = ["نوع الخدمة", "متوسط المدة"]
        dur_data = dur_data.sort_values("متوسط المدة", ascending=True)
        fig = px.bar(dur_data, x="متوسط المدة", y="نوع الخدمة", orientation="h", color="متوسط المدة", color_continuous_scale=["#fef3c7", "#d97706"])
        fig.update_layout(height=210, margin=dict(l=5, r=5, t=10, b=5), showlegend=False, yaxis=dict(tickfont=dict(size=9)), xaxis=dict(tickfont=dict(size=9), title="أيام"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("بيانات المدة غير متوفرة")
    st.markdown('</div>', unsafe_allow_html=True)

r7, r8 = st.columns(2)
with r7:
    st.markdown('<div class="box"><div class="box-title">📅 توزيع الطلبات حسب أيام الأسبوع</div>', unsafe_allow_html=True)
    if "اليوم" in df_f.columns:
        day_order = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        day_ar = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الاثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}
        day_counts = df_f["اليوم"].value_counts().reindex(day_order).dropna().reset_index()
        day_counts.columns = ["اليوم", "العدد"]
        day_counts["اليوم"] = day_counts["اليوم"].map(day_ar)
        fig = px.bar(day_counts, x="اليوم", y="العدد", color="العدد", color_continuous_scale=["#d1fae5", "#065f46"])
        fig.update_layout(height=200, margin=dict(l=5, r=5, t=10, b=5), showlegend=False, xaxis=dict(tickfont=dict(size=10)), yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("بيانات الأيام غير متوفرة")
    st.markdown('</div>', unsafe_allow_html=True)

with r8:
    st.markdown('<div class="box"><div class="box-title">🔄 توزيع المراحل الأكثر تكراراً</div>', unsafe_allow_html=True)
    stages = df_f["وصف المرحلة"].value_counts().reset_index().head(12)
    stages.columns = ["المرحلة", "العدد"]
    fig = px.bar(stages, x="العدد", y="المرحلة", orientation="h", color="العدد", color_continuous_scale=["#e0f2fe", "#0369a1"])
    fig.update_layout(height=200, margin=dict(l=5, r=5, t=10, b=5), showlegend=False, yaxis=dict(tickfont=dict(size=8)), xaxis=dict(tickfont=dict(size=9)))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

if "مدة الإنجاز (أيام)" in df_f.columns:
    st.markdown('<div class="section-title">⏱️ تحليل مدة الإنجاز</div>', unsafe_allow_html=True)
    r9, r10 = st.columns(2)
    with r9:
        st.markdown('<div class="box"><div class="box-title">📈 توزيع مدة الإنجاز (أيام)</div>', unsafe_allow_html=True)
        dur_valid = df_f["مدة الإنجاز (أيام)"].dropna()
        dur_valid = dur_valid[dur_valid > 0]
        if len(dur_valid) > 0:
            fig = px.histogram(dur_valid, nbins=25, color_discrete_sequence=["#15803d"])
            fig.update_layout(height=200, margin=dict(l=5, r=5, t=10, b=5), xaxis=dict(title="أيام", tickfont=dict(size=9)), yaxis=dict(tickfont=dict(size=9)))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات مدة إنجاز كافية")
        st.markdown('</div>', unsafe_allow_html=True)
    with r10:
        st.markdown('<div class="box"><div class="box-title">📊 أداء الجهات (متوسط مدة الإنجاز)</div>', unsafe_allow_html=True)
        if "الجهة" in df_f.columns:
            ent_dur = df_f[df_f["تصنيف"] == "منجز"].groupby("الجهة")["مدة الإنجاز (أيام)"].agg(["mean", "count"]).dropna().reset_index()
            ent_dur.columns = ["الجهة", "متوسط المدة", "العدد"]
            ent_dur = ent_dur[ent_dur["العدد"] >= 3].sort_values("متوسط المدة", ascending=True)
            if len(ent_dur) > 0:
                fig = px.bar(ent_dur, x="متوسط المدة", y="الجهة", orientation="h", color="متوسط المدة", color_continuous_scale=["#dcfce7", "#15803d"], text="متوسط المدة")
                fig.update_traces(texttemplate='%{x:.0f} يوم', textposition='outside', textfont=dict(size=9))
                fig.update_layout(height=200, margin=dict(l=5, r=40, t=10, b=5), showlegend=False, yaxis=dict(tickfont=dict(size=9)), xaxis=dict(tickfont=dict(size=9)))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("لا توجد بيانات كافية")
        else:
            st.info("بيانات الجهة غير متوفرة")
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">📋 الجدول التفصيلي</div>', unsafe_allow_html=True)
st.markdown('<div class="box">', unsafe_allow_html=True)
cols_show = [c for c in ["رقم طلب الخدمة", "نوع الخدمة", "وصف المرحلة", "تصنيف", "الجهة", "تاريخ الطلب ميلادي", "تاريخ المراجعة ميلادي", "مدة الإنجاز (أيام)", "السنة"] if c in df_f.columns]
if cols_show:
    display_df = df_f[cols_show].copy()
    for dcol in ["تاريخ الطلب ميلادي", "تاريخ المراجعة ميلادي"]:
        if dcol in display_df.columns:
            display_df[dcol] = display_df[dcol].dt.strftime("%Y-%m-%d")
    st.dataframe(display_df, use_container_width=True, height=250)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown(f'<div class="footer">أمانة منطقة الرياض — قطاع الغرب © {datetime.now().year} | جميع الحقوق محفوظة</div>', unsafe_allow_html=True)
