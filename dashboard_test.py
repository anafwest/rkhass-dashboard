import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

st.set_page_config(page_title="تجريبي - التصنيف", page_icon="🧪", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@300;400;500;600;700;800&display=swap');
    * { font-family: 'Noto Sans Arabic', sans-serif !important; }
    .main { direction: rtl; }
    .stApp { direction: rtl; background: #f0f2f6; }
    .block-container { padding: 0.5rem 1rem !important; max-width: 100% !important; }
    .header-bar { background: linear-gradient(135deg, #0d3320 0%, #1a5c3a 50%, #0d3320 100%); padding: 14px 24px; border-radius: 12px; color: white; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(13,51,32,0.3); }
    .header-bar h1 { font-size: 20px; font-weight: 800; margin: 0; }
    .header-bar .sub { font-size: 11px; opacity: 0.85; margin: 2px 0 0 0; font-weight: 300; }
    .header-bar .badge { background: rgba(255,255,255,0.15); padding: 3px 10px; border-radius: 20px; font-size: 10px; font-weight: 600; }
    .box { background: white; border-radius: 10px; padding: 12px; box-shadow: 0 1px 6px rgba(0,0,0,0.04); border: 1px solid #e8ecf0; margin-bottom: 8px; }
    .box-title { font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 2px solid #f1f5f9; }
    .section-title { font-size: 15px; font-weight: 700; color: #0d3320; margin: 12px 0 8px 0; padding-right: 8px; border-right: 4px solid #15803d; padding-left: 8px; }
    .footer { text-align: center; color: #94a3b8; font-size: 10px; padding: 10px 0 4px 0; border-top: 1px solid #e8ecf0; margin-top: 10px; }
    .kpi { background: white; border-radius: 10px; padding: 12px 10px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e8ecf0; position: relative; overflow: hidden; }
    .kpi-val { font-size: 26px; font-weight: 800; direction: ltr; display: inline-block; }
    .kpi-lbl { font-size: 11px; color: #64748b; margin-top: 2px; font-weight: 600; }
    .kpi-sub { font-size: 9px; color: #94a3b8; margin-top: 1px; }
    .kpi-bar { height: 3px; border-radius: 0 0 10px 10px; position: absolute; bottom: 0; left: 0; right: 0; }
</style>
""", unsafe_allow_html=True)

# ======================== تحميل البيانات ====================
if "df" not in st.session_state:
    if os.path.exists("data.xlsx"):
        df = pd.read_excel("data.xlsx", engine="openpyxl")
        cols = list(df.columns)
        col_rename = {}
        for c in cols:
            cs = c.strip()
            if "ميلادي" in cs and "تاريخ" in cs and "طلب" in cs:
                col_rename[c] = "تاريخ الطلب ميلادي"
            elif "ميلادي" in cs and "تاريخ" in cs and "مراجعة" in cs:
                col_rename[c] = "تاريخ المراجعة ميلادي"
        df.rename(columns=col_rename, inplace=True)
        for dcol in ["تاريخ الطلب ميلادي", "تاريخ المراجعة ميلادي"]:
            if dcol in df.columns:
                df[dcol] = pd.to_datetime(df[dcol].astype(str), format="%d/%m/%Y", errors="coerce")
        if "تاريخ الطلب ميلادي" in df.columns:
            df["اليوم"] = df["تاريخ الطلب ميلادي"].dt.day_name()
            if "تاريخ المراجعة ميلادي" in df.columns:
                df["مدة الإنجاز (أيام)"] = (df["تاريخ المراجعة ميلادي"] - df["تاريخ الطلب ميلادي"]).dt.days
                df["مدة الإنجاز (أيام)"] = df["مدة الإنجاز (أيام)"].clip(lower=0)
        if "السنة" not in df.columns and "سنه الرخصة" in df.columns:
            df["السنة"] = df["سنه الرخصة"]
        if "السنة" in df.columns:
            df["السنة"] = df["السنة"].astype(str)
        st.session_state["df"] = df

if "df" not in st.session_state:
    st.warning("لا يوجد ملف بيانات"); st.stop()

df = st.session_state["df"]

# ======================== التصنيف ====================
stages_col = "وصف المرحلة"

stages_done = [
    "تم الاطلاع", "إعتماد رئيس البلدية لشهادة اتمام بناء", "اعتماد رئيس الجهة",
    "تم تنفيذ التعديل", "منجز",
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
    "طلب تعديل من المستفيد",
    "ارجاع طلب تقرير فنى الى رئيس القسم الفنى",
    "ارجاع من المساح", "اصدار تقرير فني للطلب المحول", "إصدار تقرير فني للطلب المحول",
    "تحويل الطلب للقسم الفني", "تحويل الطلب للمراقب الفني",
    "تحويل الطلب للمراقب الفنى لاصدار شهاده اتمام البناء",
    "تحويل الطلب لمدير الإدارة المركزية لرقابة المباني والمنشآت",
    "تحويل الى رئيس قسم الرخص (المشرف)", "استلام معد المحضر الفنى",
]
stages_stopped = ["ايقاف"]
stages_rejected = ["مرفوض"]
stages_new = ["جديد"]

def classify(stage):
    if pd.isna(stage) or str(stage).strip() == "":
        return "غير محدد"
    s = str(stage).strip()
    if s in stages_done: return "منجز"
    if s in stages_returned: return "معاد للمستفيد"
    if s in stages_stopped: return "ايقاف"
    if s in stages_rejected: return "مرفوض"
    if s in stages_new: return "جديد"
    if s in stages_in_progress: return "تحت الإجراء"
    return "غير محدد"

df["تصنيف"] = df[stages_col].apply(classify)

# ======================== حسابات ====================
total = len(df)
done = (df["تصنيف"] == "منجز").sum()
returned = (df["تصنيف"] == "معاد للمستفيد").sum()
in_prog = (df["تصنيف"] == "تحت الإجراء").sum()
rejected = (df["تصنيف"] == "مرفوض").sum()
stopped = (df["تصنيف"] == "ايقاف").sum()
new = (df["تصنيف"] == "جديد").sum()
unspecified = (df["تصنيف"] == "غير محدد").sum()

done_pct = round(done / total * 100, 1) if total else 0
ret_pct = round(returned / total * 100, 1) if total else 0
in_pct = round(in_prog / total * 100, 1) if total else 0
rej_pct = round(rejected / total * 100, 1) if total else 0
stop_pct = round(stopped / total * 100, 1) if total else 0
new_pct = round(new / total * 100, 1) if total else 0

total_done = done + returned + rejected + stopped
total_done_pct = round(total_done / total * 100, 1) if total else 0

avg_duration = 0
if "مدة الإنجاز (أيام)" in df.columns:
    total_duration = df["مدة الإنجاز (أيام)"].dropna().sum()
    avg_duration = int(total_duration / total) if total > 0 else 0

# ======================== الهيدر ====================
st.markdown(f"""
<div class="header-bar">
    <div>
        <h1>🧪 مؤشر أداء رخص البناء — تجريبي</h1>
        <p class="sub">آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')} | الإجمالي: {total:,} سجل</p>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
        <span class="badge">تجريبي</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ======================== KPIs ====================
cols_per_row = 5
kpi_items = [
    (f"{total:,}", "📋 إجمالي الطلبات", "في الفترة المحددة", "#1e293b", "#64748b"),
    (f"{total_done:,}", "✅ المنجز الكلي", f"{total_done_pct}% (منجز + معاد + مرفوض + ايقاف)", "#15803d", "linear-gradient(90deg,#22c55e,#15803d)"),
    (f"{done:,}", "   منجز فقط", f"{done_pct}%", "#059669", "#059669"),
    (f"{returned:,}", "🔄 معاد للمستفيد", f"{ret_pct}%", "#2563eb", "linear-gradient(90deg,#60a5fa,#2563eb)"),
    (f"{in_prog:,}", "⚙️ تحت الإجراء", f"{in_pct}%", "#d97706", "linear-gradient(90deg,#fbbf24,#d97706)"),
    (f"{new:,}", "🆕 جديد", f"{new_pct}%", "#7c3aed", "linear-gradient(90deg,#a78bfa,#7c3aed)"),
    (f"{rejected + stopped:,}", "❌ مرفوض + ايقاف", f"{round(rej_pct + stop_pct, 1)}%", "#dc2626", "linear-gradient(90deg,#f87171,#dc2626)"),
]
kpi_html = ""
for val, lbl, sub, color, bar in kpi_items:
    kpi_html += f'''<div class="kpi"><div class="kpi-val" style="color:{color}">{val}</div><div class="kpi-lbl">{lbl}</div><div class="kpi-sub">{sub}</div><div class="kpi-bar" style="background:{bar}"></div></div>'''
st.markdown(f'<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:12px;">{kpi_html}</div>', unsafe_allow_html=True)

metric_items = [
    (f"{avg_duration} يوم", "⏱️ متوسط مدة الإنجاز", "#15803d"),
    (f"{total_done_pct}%", "📈 نسبة المنجز الكلي", "#15803d"),
    (f"{in_pct}%", "⚙️ نسبة تحت الإجراء", "#d97706"),
]
metric_html = ""
for val, lbl, color in metric_items:
    metric_html += f'''<div style="flex:1;background:white;border-radius:10px;padding:12px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.04);border:1px solid #e8ecf0;"><div style="font-size:20px;font-weight:800;color:{color};direction:ltr">{val}</div><div style="font-size:10px;color:#64748b;font-weight:600">{lbl}</div></div>'''
st.markdown(f'<div style="display:flex;gap:12px;margin-bottom:10px;">{metric_html}</div>', unsafe_allow_html=True)

# ======================== ملخص ====================
st.markdown(f"""<div style="display:flex;gap:12px;margin-bottom:10px;">
    <div style="flex:1;background:white;border-radius:10px;padding:12px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.04);border:1px solid #e8ecf0;"><div style="font-size:20px;font-weight:800;color:#15803d;direction:ltr">{avg_duration} يوم</div><div style="font-size:10px;color:#64748b;font-weight:600">⏱️ متوسط مدة الإنجاز</div></div>
    <div style="flex:1;background:white;border-radius:10px;padding:12px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.04);border:1px solid #e8ecf0;"><div style="font-size:20px;font-weight:800;color:#15803d;direction:ltr">{done_pct}%</div><div style="font-size:10px;color:#64748b;font-weight:600">📈 نسبة الإنجاز</div></div>
    <div style="flex:1;background:white;border-radius:10px;padding:12px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.04);border:1px solid #e8ecf0;"><div style="font-size:20px;font-weight:800;color:#dc2626;direction:ltr">{round(ret_pct + rej_pct + stop_pct, 1)}%</div><div style="font-size:10px;color:#64748b;font-weight:600">⚠️ نسبة الإعادة والرفض والايقاف</div></div>
</div>""", unsafe_allow_html=True)

# ======================== أزرار التصفية ====================
COLORS = {
    "منجز": "#15803d", "معاد للمستفيد": "#2563eb", "تحت الإجراء": "#d97706",
    "مرفوض": "#dc2626", "ايقاف": "#9333ea", "جديد": "#7c3aed", "غير محدد": "#94a3b8"
}
filter_labels = {"الكل": "الكل", "منجز": "✅ منجز", "معاد للمستفيد": "🔄 معاد للمستفيد", "تحت الإجراء": "⚙️ تحت الإجراء", "مرفوض": "❌ مرفوض", "ايقاف": "⏸️ ايقاف", "جديد": "🆕 جديد", "غير محدد": "❓ غير محدد"}
filter_options = ["الكل", "منجز", "معاد للمستفيد", "تحت الإجراء", "مرفوض", "ايقاف", "جديد", "غير محدد"]
filter_counts = [total, done, returned, in_prog, rejected, stopped, new, unspecified]

filter_cols = st.columns(8)
for i, (opt, cnt) in enumerate(zip(filter_options, filter_counts)):
    with filter_cols[i]:
        label = f"{filter_labels[opt]} ({cnt:,})"
        is_active = st.session_state.get("filter_stage", "الكل") == opt
        if st.button(label, key=f"btn_{opt}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.filter_stage = opt
            st.rerun()

if st.session_state.get("filter_stage", "الكل") != "الكل":
    df = df[df["تصنيف"] == st.session_state.filter_stage]

st.markdown(f'<div class="section-title">📊 عرض: {filter_labels.get(st.session_state.get("filter_stage", "الكل"), "الكل")} — {len(df):,} سجل</div>', unsafe_allow_html=True)

# ======================== الرسوم ====================
st.markdown('<div class="section-title">📈 التوزيعات والاتجاهات</div>', unsafe_allow_html=True)
r1, r2, r3 = st.columns(3)

with r1:
    st.markdown('<div class="box"><div class="box-title">🍩 توزيع الطلبات حسب التصنيف</div>', unsafe_allow_html=True)
    pie_data = df["تصنيف"].value_counts().reset_index()
    pie_data.columns = ["الحالة", "العدد"]
    color_map_pie = COLORS
    fig = px.pie(pie_data, names="الحالة", values="العدد", hole=0.55, color="الحالة", color_discrete_map=color_map_pie)
    fig.update_layout(height=220, margin=dict(l=5, r=5, t=10, b=5), showlegend=True, legend=dict(font=dict(size=9), orientation="h", y=-0.1))
    fig.update_traces(textposition='inside', textinfo='percent', textfont_size=10, marker=dict(line=dict(color='white', width=2)))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with r2:
    st.markdown('<div class="box"><div class="box-title">📊 توزيع الطلبات حسب نوع الخدمة</div>', unsafe_allow_html=True)
    if "نوع الخدمة" in df.columns:
        svc = df["نوع الخدمة"].value_counts().reset_index()
        svc.columns = ["الخدمة", "العدد"]
        fig = px.bar(svc, x="الخدمة", y="العدد", color="العدد", color_continuous_scale=["#bbf7d0", "#15803d"])
        fig.update_layout(height=220, margin=dict(l=5, r=5, t=10, b=40), showlegend=False, xaxis=dict(tickfont=dict(size=9), tickangle=-30), yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("بيانات نوع الخدمة غير متوفرة")
    st.markdown('</div>', unsafe_allow_html=True)

with r3:
    st.markdown('<div class="box"><div class="box-title">🏛️ توزيع الطلبات حسب الجهة</div>', unsafe_allow_html=True)
    if "الجهة" in df.columns:
        ent = df["الجهة"].value_counts().reset_index()
        ent.columns = ["الجهة", "العدد"]
        fig = px.bar(ent, x="العدد", y="الجهة", orientation="h", color="العدد", color_continuous_scale=["#bbf7d0", "#0d3320"])
        fig.update_layout(height=220, margin=dict(l=5, r=5, t=10, b=5), showlegend=False, yaxis=dict(tickfont=dict(size=9)), xaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("بيانات الجهة غير متوفرة")
    st.markdown('</div>', unsafe_allow_html=True)

# ======================== التصنيف حسب السنة ====================
st.markdown('<div class="section-title">📈 مقارنة التصنيفات حسب السنة</div>', unsafe_allow_html=True)
st.markdown('<div class="box">', unsafe_allow_html=True)
if "السنة" in df.columns:
    cat = df.groupby(["السنة", "تصنيف"]).size().reset_index(name="العدد")
    fig = px.bar(cat, x="السنة", y="العدد", color="تصنيف", barmode="stack", color_discrete_map=COLORS)
    fig.update_layout(height=250, legend=dict(font=dict(size=8), orientation="h", y=-0.15), xaxis=dict(tickfont=dict(size=9)), yaxis=dict(tickfont=dict(size=9)))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("بيانات السنة غير متوفرة")
st.markdown('</div>', unsafe_allow_html=True)

# ======================== المراحل الأكثر تكراراً ====================
st.markdown('<div class="section-title">🔄 توزيع المراحل الأكثر تكراراً (وفقاً لوصف المرحلة)</div>', unsafe_allow_html=True)
st.markdown('<div class="box">', unsafe_allow_html=True)
stages_vc = df[stages_col].value_counts().reset_index().head(12)
stages_vc.columns = ["المرحلة", "العدد"]
fig = px.bar(stages_vc, x="العدد", y="المرحلة", orientation="h", color="العدد", color_continuous_scale=["#e0f2fe", "#0369a1"])
fig.update_layout(height=200, margin=dict(l=5, r=5, t=10, b=5), showlegend=False, yaxis=dict(tickfont=dict(size=8)), xaxis=dict(tickfont=dict(size=9)))
st.plotly_chart(fig, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ======================== مدة الإنجاز ====================
if "مدة الإنجاز (أيام)" in df.columns:
    st.markdown('<div class="section-title">⏱️ تحليل مدة الإنجاز</div>', unsafe_allow_html=True)
    r6, r7 = st.columns(2)
    with r6:
        st.markdown('<div class="box"><div class="box-title">⏱️ متوسط مدة الإنجاز حسب نوع الخدمة</div>', unsafe_allow_html=True)
        if "نوع الخدمة" in df.columns:
            dur_data = df[df["تصنيف"] == "منجز"].groupby("نوع الخدمة")["مدة الإنجاز (أيام)"].mean().dropna().reset_index()
            dur_data.columns = ["نوع الخدمة", "متوسط المدة"]
            dur_data = dur_data.sort_values("متوسط المدة", ascending=True)
            if len(dur_data) > 0:
                fig = px.bar(dur_data, x="متوسط المدة", y="نوع الخدمة", orientation="h", color="متوسط المدة", color_continuous_scale=["#fef3c7", "#d97706"])
                fig.update_layout(height=210, margin=dict(l=5, r=5, t=10, b=5), showlegend=False, yaxis=dict(tickfont=dict(size=9)), xaxis=dict(tickfont=dict(size=9), title="أيام"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("لا توجد بيانات كافية")
        else:
            st.info("بيانات نوع الخدمة غير متوفرة")
        st.markdown('</div>', unsafe_allow_html=True)
    with r7:
        st.markdown('<div class="box"><div class="box-title">📈 توزيع مدة الإنجاز (أيام)</div>', unsafe_allow_html=True)
        dur_valid = df["مدة الإنجاز (أيام)"].dropna()
        dur_valid = dur_valid[dur_valid > 0]
        if len(dur_valid) > 0:
            fig = px.histogram(dur_valid, nbins=25, color_discrete_sequence=["#15803d"])
            fig.update_layout(height=210, margin=dict(l=5, r=5, t=10, b=5), xaxis=dict(title="أيام", tickfont=dict(size=9)), yaxis=dict(tickfont=dict(size=9)))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات مدة إنجاز كافية")
        st.markdown('</div>', unsafe_allow_html=True)

# ======================== الجدول ====================
st.markdown('<div class="section-title">📋 الجدول التفصيلي</div>', unsafe_allow_html=True)
st.markdown('<div class="box">', unsafe_allow_html=True)
cols_show = [c for c in ["رقم طلب الخدمة", "نوع الخدمة", stages_col, "تصنيف", "الجهة", "تاريخ الطلب ميلادي", "تاريخ المراجعة ميلادي", "مدة الإنجاز (أيام)", "السنة"] if c in df.columns]
if cols_show:
    display_df = df[cols_show].copy()
    for dcol in ["تاريخ الطلب ميلادي", "تاريخ المراجعة ميلادي"]:
        if dcol in display_df.columns:
            display_df[dcol] = display_df[dcol].dt.strftime("%Y-%m-%d")
    st.dataframe(display_df, use_container_width=True, height=300)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown(f'<div class="footer">أمانة منطقة الرياض — قطاع الغرب | نسخة تجريبية © {datetime.now().year}</div>', unsafe_allow_html=True)
