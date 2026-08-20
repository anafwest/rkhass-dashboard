import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os, shutil, glob, hashlib, hmac

# ── Config ──
st.set_page_config(page_title="داشبورد رخص البناء", page_icon="", layout="wide", initial_sidebar_state="expanded")

# ── Authentication ──
PASSWORD = st.secrets.get("password", "1234")

def check_password():
    if st.session_state.get("authenticated", False):
        return True
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""<div style='text-align:center;margin-top:80px'>
            <h2>داشبورد رخص البناء</h2><p>أمانة منطقة الرياض - قطاع الغرب</p></div>""", unsafe_allow_html=True)
        pw = st.text_input("كلمة المرور", type="password", placeholder="أدخل كلمة المرور")
        if st.button("دخول", use_container_width=True):
            if pw == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة")
    return False

if not check_password():
    st.stop()

# ── Data Loader with Backup ──
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

@st.cache_data(ttl=300)
def load_data():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    found = None
    for f in ["data.xls", "الطلبات.xls", "data.xlsx"]:
        p = os.path.join(DATA_DIR, f)
        if os.path.exists(p):
            try:
                if f.endswith(".xlsx"):
                    df = pd.read_excel(p)
                else:
                    try:
                        df = pd.read_excel(p)
                    except:
                        dfs = pd.read_html(p, encoding="cp1256")
                        df = dfs[0]
                found = p
                break
            except:
                continue
    if found is None:
        return None

    rename = {}
    for c in df.columns:
        cs = c.strip()
        if cs == "طلب الخدمة": rename[c] = "رقم طلب الخدمة"
        elif cs == "الجهه": rename[c] = "الجهة"
        elif cs == "الملالك": rename[c] = "المالك"
        elif cs == "سنة الرخصة": rename[c] = "السنة الهجرية"
        elif cs == "تاريخ الطلب" and "ميلادي" not in cs: rename[c] = "تاريخ الطلب هجري"
        elif cs == "تاريخ المراجعة" and "ميلادي" not in cs: rename[c] = "تاريخ المراجعة هجري"
    df.rename(columns=rename, inplace=True)

    if "تاريخ الطلب ميلادي" in df.columns:
        df["تاريخ الطلب ميلادي"] = pd.to_datetime(df["تاريخ الطلب ميلادي"].astype(str), format="%d/%m/%Y", errors="coerce")
    if "تاريخ المراجعة ميلادي" in df.columns:
        df["تاريخ المراجعة ميلادي"] = pd.to_datetime(df["تاريخ المراجعة ميلادي"].astype(str), format="%d/%m/%Y", errors="coerce")
    if "السنة" in df.columns:
        df["السنة"] = df["السنة"].astype(str)

    # Backup with timestamp
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"data_{ts}.xls"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        try:
            shutil.copy2(found, backup_path)
        except:
            pass
    # Keep last 30 backups
    all_backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "data_*.xls")))
    for old in all_backups[:-30]:
        try: os.remove(old)
        except: pass

    return df

df = load_data()
if df is None or df.empty:
    st.error("لم يتم العثور على ملف بيانات. يرجى التأكد من وجود ملف البيانات.")
    st.stop()

def classify_stage(stage):
    if any(k in stage for k in ["المستفيد", "وثائق", "وثاق"]):
        return "معاد للمستفيد"
    if any(k in stage for k in [
        "مرفوض", "مرفوق", "تم الاطلاع", "اعتماد", "إعتماد",
        "رئيس البلدية", "رئيس الجهة", "منجز", "تنفيذ التعديل",
        "تحرير", "اصدار تقرير", "رد الى", "رفض رئيس",
        "القرار الفنى", "القرار الفني", "شهادة اتمام",
    ]):
        return "منجز"
    return "تحت الإجراء"

df["التصنيف"] = df["وصف المرحلة"].apply(classify_stage)

if "filter_stage" not in st.session_state:
    st.session_state.filter_stage = "الكل"

# ── CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@300;400;600;700;800&display=swap');
    * { font-family: 'Noto Sans Arabic', sans-serif !important; }
    .main { direction: rtl; } .stApp { direction: rtl; background: #f0f2f5; }
    .block-container { padding: 0.3rem 1rem !important; max-width: 100% !important; }
    #MainMenu, header, footer { display: none !important; }
    .stAppDeployButton, .stActionButton, .stDecoration { display: none !important; }
    [data-testid="collapsedControl"] { position: absolute; opacity: 0; width: 1px; height: 1px; overflow: hidden; }
    section[data-testid="stSidebarContent"] + div { display: none !important; }
    .header { background: linear-gradient(135deg, #0d3b1e, #1a6b33); padding: 10px 18px; border-radius: 10px; color: white; margin-bottom: 6px; display: flex; align-items: center; justify-content: space-between; }
    .header h1 { font-size: 18px; font-weight: 800; margin: 0; }
    .header p { font-size: 10px; opacity: 0.8; margin: 2px 0 0 0; }
    .kpi-row { display: flex; gap: 6px; margin-bottom: 6px; }
    .kpi-card { flex: 1; background: white; border-radius: 8px; padding: 8px 6px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.03); border: 1px solid #e8ecf0; }
    .kpi-number { font-size: 20px; font-weight: 800; color: #0d3b1e; direction: ltr; }
    .kpi-label { font-size: 9px; color: #687385; font-weight: 600; }
    .kpi-strip-1 { border-top: 3px solid #687385; }
    .kpi-strip-2 { border-top: 3px solid #1a6b33; }
    .kpi-strip-3 { border-top: 3px solid #d4a11e; }
    .kpi-strip-4 { border-top: 3px solid #e67e22; }
    .box { background: white; border-radius: 8px; padding: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.02); border: 1px solid #e8ecf0; margin-bottom: 4px; }
    div[data-testid="stSidebar"] { direction: rtl; }
    .footer { text-align: center; color: #9aa2af; font-size: 9px; padding: 6px 0 0 0; border-top: 1px solid #e8ecf0; margin-top: 6px; }
    .stButton > button { font-size: 12px !important; font-weight: 600 !important; padding: 2px 6px !important; }
    #eyeBtn { background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); color: white; border-radius: 20px; font-size: 12px; padding: 2px 10px; cursor: pointer; backdrop-filter: blur(4px); white-space: nowrap; }
    #eyeBtn:hover { background: rgba(255,255,255,0.3); }
</style>
""", unsafe_allow_html=True)

# ── Header ──
hdr = st.columns([1, 2, 1])
with hdr[0]:
    st.markdown("""
<button id="eyeBtn" onclick="var b=document.querySelector('[data-testid=\\'collapsedControl\\']');if(b)b.click();">👁 إخفاء</button>
<script>(function(){
    var b = document.getElementById('eyeBtn'); if(!b) return;
    var update = function(){
        var s = document.querySelector('[data-testid="stSidebar"]');
        b.innerHTML = s && (s.style.display==='none'||s.style.visibility==='hidden') ? '👁‍🗨 إظهار' : '👁 إخفاء';
    };
    b.onclick = function(){ var c = document.querySelector('[data-testid="collapsedControl"]'); if(c) c.click(); setTimeout(update,50); setTimeout(update,200); };
    update();
})();</script>""", unsafe_allow_html=True)
with hdr[1]:
    st.markdown(f"""<div class="header"><div><h1>داشبورد رخص البناء - قطاع الغرب</h1>
<p>أمانة منطقة الرياض | {datetime.now().strftime('%Y-%m-%d %H:%M')} | إجمالي {len(df):,} طلب</p></div></div>""", unsafe_allow_html=True)

# ── Sidebar ──
months_list = sorted(df["تاريخ الطلب ميلادي"].dt.to_period("M").astype(str).unique()) if "تاريخ الطلب ميلادي" in df.columns else []
min_d = df["تاريخ الطلب ميلادي"].min()
max_d = df["تاريخ الطلب ميلادي"].max()

with st.sidebar:
    st.markdown("## تصفية")
    filter_mode = st.segmented_control("الفترة", ["الكل", "شهر", "مخصص"], default="الكل", selection_mode="single")
    if filter_mode == "الكل" or not filter_mode:
        sf, ef = min_d, max_d
        st.caption(f"{min_d.date()} - {max_d.date()}")
    elif filter_mode == "مخصص" and pd.notna(min_d) and pd.notna(max_d):
        dr = st.date_input("الفترة", [min_d.date(), max_d.date()], min_value=min_d.date(), max_value=max_d.date(), format="YYYY-MM-DD")
        sf = datetime.combine(dr[0], datetime.min.time()) if len(dr) == 2 else min_d
        ef = datetime.combine(dr[1], datetime.max.time()) if len(dr) == 2 else max_d
        st.caption(f"{sf.date()} - {ef.date()}")
    elif filter_mode == "شهر" and months_list:
        sel_month = st.selectbox("اختر الشهر", months_list, index=len(months_list)-1)
        sf = datetime.strptime(sel_month + "-01", "%Y-%m-%d")
        import calendar
        last_day = calendar.monthrange(sf.year, sf.month)[1]
        ef = sf.replace(day=last_day, hour=23, minute=59, second=59)
        st.caption(f"{sel_month} ({sf.date()} - {ef.date()})")
    else:
        sf, ef = min_d, max_d
    st.markdown("---")
    df_temp = df.copy()
    if "تاريخ الطلب ميلادي" in df.columns:
        df_temp = df_temp[(df_temp["تاريخ الطلب ميلادي"] >= sf) & (df_temp["تاريخ الطلب ميلادي"] <= ef)]
    flt_خدمة = st.multiselect("الخدمة", df_temp["نوع الخدمة"].unique() if "نوع الخدمة" in df_temp.columns else [], placeholder="الكل")
    flt_جهة = st.multiselect("الجهة", df_temp["الجهة"].unique() if "الجهة" in df_temp.columns else [], placeholder="الكل")
    flt_سنة = st.multiselect("السنة", sorted(df_temp["السنة"].unique()) if "السنة" in df_temp.columns else [], placeholder="الكل")

# ── Filter ──
df_display = df.copy()
if st.session_state.filter_stage != "الكل":
    df_display = df_display[df_display["التصنيف"] == st.session_state.filter_stage]
if "تاريخ الطلب ميلادي" in df.columns:
    df_display = df_display[(df_display["تاريخ الطلب ميلادي"] >= sf) & (df_display["تاريخ الطلب ميلادي"] <= ef)]
if flt_خدمة: df_display = df_display[df_display["نوع الخدمة"].isin(flt_خدمة)]
if flt_جهة: df_display = df_display[df_display["الجهة"].isin(flt_جهة)]
if "السنة" in df.columns and flt_سنة: df_display = df_display[df_display["السنة"].isin(flt_سنة)]

# ── KPIs ──
ftotal = len(df_display)
fcomp = (df_display["التصنيف"] == "منجز").sum()
finprog = (df_display["التصنيف"] == "تحت الإجراء").sum()
freturned = (df_display["التصنيف"] == "معاد للمستفيد").sum()
fcomp_pct = round(fcomp / ftotal * 100, 1) if ftotal else 0
finp_pct = round(finprog / ftotal * 100, 1) if ftotal else 0
fret_pct = round(freturned / ftotal * 100, 1) if ftotal else 0
fmonths = df_display["تاريخ الطلب ميلادي"].dt.to_period("M").nunique() if "تاريخ الطلب ميلادي" in df_display.columns and ftotal else 1
favg = round(ftotal / fmonths, 0) if fmonths else 0

st.markdown(f"""<div class="kpi-row">
    <div class="kpi-card kpi-strip-1"><div class="kpi-number">{ftotal:,}</div><div class="kpi-label">إجمالي الطلبات</div></div>
    <div class="kpi-card kpi-strip-2"><div class="kpi-number">{fcomp:,}</div><div class="kpi-label">منجز ({fcomp_pct}%)</div></div>
    <div class="kpi-card kpi-strip-4"><div class="kpi-number">{freturned:,}</div><div class="kpi-label">معاد للمستفيد ({fret_pct}%)</div></div>
    <div class="kpi-card kpi-strip-3"><div class="kpi-number">{finprog:,}</div><div class="kpi-label">تحت الإجراء ({finp_pct}%)</div></div>
    <div class="kpi-card kpi-strip-1"><div class="kpi-number">{int(favg):,}</div><div class="kpi-label">متوسط شهري ({fmonths} شهر)</div></div>
</div>""", unsafe_allow_html=True)

# ── Filter Buttons ──
total_all = len(df)
comp_all = (df["التصنيف"] == "منجز").sum()
inp_all = (df["التصنيف"] == "تحت الإجراء").sum()
ret_all = (df["التصنيف"] == "معاد للمستفيد").sum()

c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button(f"الكل ({total_all:,})", use_container_width=True):
        st.session_state.filter_stage = "الكل"; st.rerun()
with c2:
    if st.button(f"منجز ({comp_all:,})", use_container_width=True):
        st.session_state.filter_stage = "منجز"; st.rerun()
with c3:
    if st.button(f"معاد للمستفيد ({ret_all:,})", use_container_width=True):
        st.session_state.filter_stage = "معاد للمستفيد"; st.rerun()
with c4:
    if st.button(f"تحت الإجراء ({inp_all:,})", use_container_width=True):
        st.session_state.filter_stage = "تحت الإجراء"; st.rerun()

# ── Charts ──
r1, r2 = st.columns(2)
with r1:
    st.markdown('<div class="box"><p style="font-size:12px;font-weight:600;margin:4px 8px">المراحل</p>', unsafe_allow_html=True)
    stages_chart = df_display["وصف المرحلة"].value_counts().reset_index()
    stages_chart.columns = ["المرحلة", "العدد"]
    fig = px.bar(stages_chart, x="المرحلة", y="العدد", color="المرحلة", color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(height=240, margin=dict(l=5, r=5, t=5, b=80), showlegend=False, xaxis=dict(tickfont=dict(size=8)), yaxis=dict(tickfont=dict(size=9)))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with r2:
    st.markdown('<div class="box"><p style="font-size:12px;font-weight:600;margin:4px 8px">الجهات</p>', unsafe_allow_html=True)
    entities = df_display["الجهة"].value_counts().reset_index() if "الجهة" in df_display.columns else None
    if entities is not None:
        entities.columns = ["الجهة", "العدد"]
        fig = px.pie(entities, names="الجهة", values="العدد", hole=0.5)
        fig.update_layout(height=240, margin=dict(l=5, r=5, t=5, b=5), legend=dict(font=dict(size=9), orientation="h", y=-0.15))
        fig.update_traces(textposition='inside', textinfo='percent', textfont_size=10)
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

r3, r4 = st.columns(2)
with r3:
    st.markdown('<div class="box"><p style="font-size:12px;font-weight:600;margin:4px 8px">التصنيف</p>', unsafe_allow_html=True)
    cat = df_display["التصنيف"].value_counts().reset_index()
    cat.columns = ["الحالة", "العدد"]
    colors = {"منجز": "#1a6b33", "تحت الإجراء": "#d4a11e", "معاد للمستفيد": "#e67e22"}
    fig = px.pie(cat, names="الحالة", values="العدد", hole=0.5, color="الحالة", color_discrete_map=colors)
    fig.update_layout(height=210, margin=dict(l=5, r=5, t=5, b=5), legend=dict(font=dict(size=9)))
    fig.update_traces(textposition='inside', textinfo='percent+label', textfont_size=11)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with r4:
    st.markdown('<div class="box"><p style="font-size:12px;font-weight:600;margin:4px 8px">الخدمات</p>', unsafe_allow_html=True)
    services = df_display["نوع الخدمة"].value_counts().reset_index() if "نوع الخدمة" in df_display.columns else None
    if services is not None:
        services.columns = ["الخدمة", "العدد"]
        fig = px.bar(services.head(10), x="العدد", y="الخدمة", orientation="h", color="العدد", color_continuous_scale="greens")
        fig.update_layout(height=210, margin=dict(l=5, r=5, t=5, b=5), showlegend=False, yaxis=dict(tickfont=dict(size=8)), xaxis=dict(tickfont=dict(size=8)))
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── Monthly Trend ──
st.markdown('<div class="box"><p style="font-size:12px;font-weight:600;margin:4px 8px">الاتجاه الشهري</p>', unsafe_allow_html=True)
if "تاريخ الطلب ميلادي" in df_display.columns:
    monthly = df_display.set_index("تاريخ الطلب ميلادي").resample("ME").size().reset_index()
    monthly.columns = ["الشهر", "العدد"]
    monthly["الشهر"] = monthly["الشهر"].dt.strftime("%m/%Y")
    fig = px.line(monthly, x="الشهر", y="العدد", markers=True)
    fig.update_layout(height=160, margin=dict(l=5, r=5, t=5, b=25), xaxis=dict(tickfont=dict(size=8)), yaxis=dict(tickfont=dict(size=8)))
    st.plotly_chart(fig, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ── Monthly Breakdown ──
st.markdown('<div class="box"><p style="font-size:12px;font-weight:600;margin:4px 8px">تحليل شهري - التصنيف لكل شهر</p>', unsafe_allow_html=True)
if "تاريخ الطلب ميلادي" in df_display.columns:
    df_m = df_display.copy()
    df_m["شهر"] = df_m["تاريخ الطلب ميلادي"].dt.to_period("M").astype(str)
    monthly_cat = df_m.groupby(["شهر", "التصنيف"]).size().reset_index(name="العدد")
    if not monthly_cat.empty:
        colors = {"منجز": "#1a6b33", "تحت الإجراء": "#d4a11e", "معاد للمستفيد": "#e67e22"}
        fig = px.bar(monthly_cat, x="شهر", y="العدد", color="التصنيف", barmode="group", color_discrete_map=colors)
        fig.update_layout(height=180, margin=dict(l=5, r=5, t=5, b=40), xaxis=dict(tickfont=dict(size=8)), yaxis=dict(tickfont=dict(size=8)), legend=dict(font=dict(size=9), orientation="h", y=-0.35))
        st.plotly_chart(fig, use_container_width=True)
    monthly_stats = df_m.groupby("شهر").agg(
        الإجمالي=("وصف المرحلة", "count"),
        منجز=("التصنيف", lambda x: (x == "منجز").sum()),
        تحت_الإجراء=("التصنيف", lambda x: (x == "تحت الإجراء").sum()),
        معاد_للمستفيد=("التصنيف", lambda x: (x == "معاد للمستفيد").sum()),
    ).reset_index()
    monthly_stats["نسبة الإنجاز"] = monthly_stats.apply(lambda r: f"{round(r['منجز']/r['الإجمالي']*100,1)}%" if r['الإجمالي'] else "0%", axis=1)
    monthly_stats.columns = ["الشهر", "الإجمالي", "منجز", "تحت الإجراء", "معاد للمستفيد", "نسبة الإنجاز"]
    st.dataframe(monthly_stats, use_container_width=True, hide_index=True, height=min(35*len(monthly_stats)+35, 300))
st.markdown('</div>', unsafe_allow_html=True)

# ── Data Table ──
st.markdown('<div class="box">', unsafe_allow_html=True)
show_cols = [c for c in ["رقم طلب الخدمة", "نوع الخدمة", "وصف المرحلة", "الجهة", "تاريخ الطلب ميلادي", "السنة", "المالك", "التصنيف"] if c in df_display.columns]
st.dataframe(df_display[show_cols] if show_cols else df_display, use_container_width=True, height=200)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="footer">أمانة منطقة الرياض - قطاع الغرب 2026</div>', unsafe_allow_html=True)
