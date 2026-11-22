import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import datetime
import os
import streamlit.components.v1 as components

# ==========================================
# ۱. تنظیمات اولیه صفحه و وضعیت برنامه
# ==========================================
st.set_page_config(page_title="سیستم جامع امانات گدام", page_icon="🏢", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'cart' not in st.session_state:
    st.session_state.cart = []

# تابع تبدیل تاریخ میلادی به هجری شمسی دقیق
def get_shamsi_today():
    now = datetime.datetime.now()
    gy, gm, gd = now.year, now.month, now.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"

# ==========================================
# ۲. راه‌اندازی دیتابیس SQLite و بارگذاری اطلاعات اکسل
# ==========================================
DB_FILE = "godam_enterprise.db"

def init_db():
    is_new = not os.path.exists(DB_FILE)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()

    # جدول تنظیمات و رمز عبور
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )""")

    # جدول نمایندگان
    c.execute("""CREATE TABLE IF NOT EXISTS representatives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    area TEXT,
                    status TEXT DEFAULT 'فعال',
                    notes TEXT
                )""")

    # جدول اجناس گدام
    c.execute("""CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT,
                    name TEXT NOT NULL UNIQUE,
                    stock INTEGER NOT NULL DEFAULT 0
                )""")

    # جدول سربرگ اسناد امانت (حواله‌ها)
    c.execute("""CREATE TABLE IF NOT EXISTS loan_docs (
                    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_number TEXT NOT NULL,
                    rep_id INTEGER,
                    loan_date TEXT,
                    notes TEXT,
                    FOREIGN KEY(rep_id) REFERENCES representatives(id)
                )""")

    # جدول اقلام هر سند امانت (پشتیبانی از چند جنس در یک سند)
    c.execute("""CREATE TABLE IF NOT EXISTS loan_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER,
                    item_id INTEGER,
                    quantity INTEGER,
                    returned_qty INTEGER DEFAULT 0,
                    lost_qty INTEGER DEFAULT 0,
                    FOREIGN KEY(doc_id) REFERENCES loan_docs(doc_id),
                    FOREIGN KEY(item_id) REFERENCES items(id)
                )""")

    # جدول ثبت وقایع و تغییرات (Audit Logs)
    c.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_time TEXT,
                    action_type TEXT,
                    details TEXT
                )""")

    # مقداردهی اولیه در صورت جدید بودن دیتابیس
    if is_new:
        c.execute("INSERT INTO settings (key, value) VALUES ('admin_user', 'admin')")
        c.execute("INSERT INTO settings (key, value) VALUES ('admin_pass', '1234')")

        # افزودن ۵ نوع جنس گدام مطابق فایل اکسل
        initial_items = [
            ("K-101", "کراچی", 50),
            ("P-102", "پلیت", 100),
            ("Y-103", "یخچال", 20),
            ("PF-104", "پلیت فریز", 150),
            ("D-105", "دبه", 80)
        ]
        c.executemany("INSERT INTO items (code, name, stock) VALUES (?, ?, ?)", initial_items)

        # افزودن هر ۲۶ نماینده از فایل اکسل شما
        initial_reps = [
            ("لعل محمد", "766808056", "ولسوالی امام صاحب", "فعال", ""),
            ("مطیع الله", "778748036", "ولسوالی امام صاحب", "فعال", ""),
            ("سفر محمد", "747182383", "ولسوالی امام صاحب", "فعال", ""),
            ("عبدالحلیم", "778048609", "ولسوالی امام صاحب", "فعال", ""),
            ("عبدالحارث", "728772172", "ولسوالی امام صاحب", "غیرفعال", ""),
            ("عین الدین", "780409454", "بندر امام صاحب", "غیرفعال", ""),
            ("یونس", "747447841", "بندر امام صاحب", "غیرفعال", ""),
            ("اسد الله", "780323176", "بندر امام صاحب", "غیرفعال", ""),
            ("نظر محمد", "783877671", "بندر امام صاحب", "غیرفعال", ""),
            ("صدیق الله", "789308250", "ترکمن ها (مرکز شهر)", "غیرفعال", ""),
            ("عبدالهادی", "798146491", "زر خرید پاچا قلندر (مرکز شهر)", "غیرفعال", ""),
            ("حبیب الله یلداش", "797148861", "ترکمن ها (مرکز شهر)", "غیرفعال", ""),
            ("عبدالبشیر", "771124933", "سرآسیاب شرکت (مرکز شهر)", "فعال", ""),
            ("عبدالجبار", "771628716", "بندر کابل (مرکز شهر)", "فعال", ""),
            ("سهراب", "788757960", "بندر کابل (مرکز شهر)", "غیرفعال", ""),
            ("نصرالله", "791575408", "شفاخانه ملکی (مرکز شهر)", "غیرفعال", ""),
            ("میرویس", "747598623", "سردوره (مرکز شهر)", "فعال", ""),
            ("خیر محمد", "771000981", "پوهنتون سلام (مرکز شهر)", "غیرفعال", ""),
            ("جمال الدین", "729364645", "زیردوره (مرکز شهر)", "غیرفعال", ""),
            ("ملنگ", "779099047", "ولسوالی خان آباد", "فعال", ""),
            ("ضیاالحق", "749455199", "ولسوالی خان آباد", "فعال", ""),
            ("نواب نورزی", "784265425", "ولسوالی علی آباد", "فعال", ""),
            ("عبدالفتاح", "780897057", "ولسوالی علی آباد", "فعال", ""),
            ("عبدالبصیر", "704785933", "ولسوالی چهار دره", "فعال", ""),
            ("انجنییر مصطفی", "703094037", "ولسوالی دشت ارچی", "فعال", ""),
            ("عبدالکریم", "765505014", "ولسوالی قلعه ذال", "فعال", "")
        ]
        c.executemany("INSERT INTO representatives (name, phone, area, status, notes) VALUES (?, ?, ?, ?, ?)", initial_reps)

        # ثبت سندهای قبلی لعل محمد از فایل اکسل (سند 1010)
        c.execute("INSERT INTO loan_docs (doc_number, rep_id, loan_date, notes) VALUES ('1010', 1, '1405/08/20', 'باقی مانده از سال گذشته')")
        doc1_id = c.lastrowid
        c.execute("INSERT INTO loan_items (doc_id, item_id, quantity, returned_qty, lost_qty) VALUES (?, 1, 15, 0, 0)", (doc1_id,))
        c.execute("INSERT INTO loan_items (doc_id, item_id, quantity, returned_qty, lost_qty) VALUES (?, 3, 2, 0, 0)", (doc1_id,))

        c.execute("INSERT INTO audit_logs (action_time, action_type, details) VALUES (?, 'راه‌اندازی سیستم', 'دیتابیس با ۲۶ نماینده و ۵ نوع جنس ایجاد شد')", (get_shamsi_today(),))

    conn.commit()
    return conn

conn = init_db()

def log_action(action_type, details):
    c = conn.cursor()
    now_str = f"{get_shamsi_today()} - {datetime.datetime.now().strftime('%H:%M')}"
    c.execute("INSERT INTO audit_logs (action_time, action_type, details) VALUES (?, ?, ?)", (now_str, action_type, details))
    conn.commit()

# ==========================================
# ۳. استایل‌دهی راست‌به‌چپ (RTL) و تم شب و روز
# ==========================================
if st.session_state.dark_mode:
    bg_color = "#0F172A"
    card_bg = "#1E293B"
    sidebar_bg = "#1E293B"
    text_main = "#F8FAFC"
    text_sub = "#94A3B8"
    border_col = "#334155"
    chart_template = "plotly_dark"
else:
    bg_color = "#F4F7FE"
    card_bg = "#FFFFFF"
    sidebar_bg = "#FFFFFF"
    text_main = "#1E293B"
    text_sub = "#64748B"
    border_col = "#E2E8F0"
    chart_template = "plotly_white"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {{
        font-family: 'Vazirmatn', Tahoma, sans-serif !important;
        direction: rtl;
        text-align: right;
    }}
    
    .stApp {{
        background-color: {bg_color};
        color: {text_main};
    }}
    
    /* چیدمان راست‌به‌چپ سایدبار و ستون‌ها */
    [data-testid="stAppViewContainer"] {{
        direction: rtl;
    }}
    section[data-testid="stSidebar"] {{
        background-color: {sidebar_bg};
        border-left: 1px solid {border_col};
        direction: rtl;
        text-align: right;
    }}
    section[data-testid="stSidebar"] * {{
        color: {text_main} !important;
        text-align: right;
    }}
    
    h1, h2, h3, h4, p, label, .stMarkdown {{
        color: {text_main} !important;
        direction: rtl;
        text-align: right;
    }}
    
    input, textarea, select {{
        direction: rtl !important;
        text-align: right !important;
    }}

    .metric-card {{
        background-color: {card_bg};
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid {border_col};
        direction: rtl;
        text-align: right;
        margin-bottom: 10px;
    }}
    .metric-title {{
        color: {text_sub};
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 6px;
    }}
    .metric-value {{
        color: {text_main};
        font-size: 24px;
        font-weight: 800;
    }}
    .metric-badge {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        margin-top: 6px;
    }}
    .badge-blue {{ background-color: #E0E7FF; color: #4338CA !important; }}
    .badge-green {{ background-color: #DCFCE7; color: #15803D !important; }}
    .badge-purple {{ background-color: #F3E8FF; color: #7E22CE !important; }}
    .badge-red {{ background-color: #FEE2E2; color: #B91C1C !important; }}

    .login-box {{
        background-color: {card_bg};
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.08);
        border: 1px solid {border_col};
        text-align: center;
        margin-top: 40px;
    }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# ۴. تابع چاپ دو نسخه A5 در یک صفحه A4 با فونت B Nazanin
# ==========================================
def generate_dual_a5_print_html(doc_number, loan_date, rep_name, rep_phone, rep_area, items_list, notes):
    rows_html = ""
    for idx, it in enumerate(items_list, 1):
        rows_html += f"""
        <tr>
            <td style="padding: 4px; border: 1px solid #475569;">{idx}</td>
            <td style="padding: 4px; border: 1px solid #475569;"><b>{it['name']}</b></td>
            <td style="padding: 4px; border: 1px solid #475569;"><b>{it['qty']} عدد</b></td>
        </tr>
        """

    def single_copy_block(copy_title):
        return f"""
        <div style="border: 2px solid #000; padding: 12px 18px; border-radius: 6px; background: #FFF; color: #000; font-family: 'B Nazanin', Nazanin, Tahoma, sans-serif; direction: rtl; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #000; padding-bottom: 5px; margin-bottom: 8px;">
                <span style="font-size: 13px; background: #E2E8F0; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{copy_title}</span>
                <span style="font-size: 19px; font-weight: bold;">سند رسمی تحویل امانات گدام</span>
                <span style="font-size: 14px;">شماره سند: <b>{doc_number}</b> | تاریخ: <b>{loan_date}</b></span>
            </div>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 14px;">
                <tr>
                    <td style="padding: 4px 8px; border: 1px solid #64748B; width: 35%;"><b>نام نماینده:</b> {rep_name}</td>
                    <td style="padding: 4px 8px; border: 1px solid #64748B; width: 30%;"><b>شماره موبایل:</b> {rep_phone if rep_phone else '---'}</td>
                    <td style="padding: 4px 8px; border: 1px solid #64748B; width: 35%;"><b>ساحه / آدرس:</b> {rep_area if rep_area else '---'}</td>
                </tr>
            </table>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 14px; text-align: center;">
                <tr style="background: #F1F5F9;">
                    <th style="padding: 4px; border: 1px solid #475569; width: 10%;">شماره</th>
                    <th style="padding: 4px; border: 1px solid #475569; width: 60%;">نوع جنس امانتی</th>
                    <th style="padding: 4px; border: 1px solid #475569; width: 30%;">تعداد تحویلی</th>
                </tr>
                {rows_html}
            </table>

            <div style="font-size: 13px; background: #FFFBEB; border: 1px solid #D97706; padding: 5px 10px; border-radius: 4px; margin-bottom: 8px; line-height: 1.5;">
                <b>تذکرات مهم:</b> اجناس فوق نزد نماینده <b>امانت</b> بوده و حق فروش یا واگذاری به غیر ندارد. نماینده مکلف به مراقبت کامل بوده و در صورت مفقودی یا خسارت، جریمه اخذ می‌گردد. <b>در وقت تسلیم‌دهی امانات، ورق ذیل را حتماً با خود داشته باشید.</b>
                {f"<br><b>ملاحظات:</b> {notes}" if notes else ""}
            </div>

            <table style="width: 100%; text-align: center; font-size: 14px; margin-top: 12px;">
                <tr>
                    <td style="width: 50%;"><b>امضاء و شصت نماینده تحویل‌گیرنده:</b> ............................</td>
                    <td style="width: 50%;"><b>مهر و امضاء مسئول گدام:</b> ............................</td>
                </tr>
            </table>
        </div>
        """

    full_html = f"""
    <div id="printableArea" style="background: white; padding: 10px; max-width: 820px; margin: auto;">
        {single_copy_block("نسخه اول: مخصوص نماینده")}
        <div style="border-top: 1px dashed #64748B; margin: 12px 0; text-align: center; font-size: 11px; color: #64748B; font-family: Tahoma;">✂️ محل برش کاغذ (دو نسخه A5 در یک صفحه A4)</div>
        {single_copy_block("نسخه دوم: مخصوص بایگانی گدام")}
    </div>
    <div style="text-align: center; margin-top: 15px;">
        <button onclick="printDiv()" style="background-color: #2563EB; color: white; border: none; padding: 12px 35px; font-size: 16px; border-radius: 8px; cursor: pointer; font-family: Tahoma; font-weight: bold;">
            🖨️ چاپ دو نسخه A5 در یک صفحه (Ctrl + P)
        </button>
    </div>
    <script>
    function printDiv() {{
        var divContents = document.getElementById("printableArea").innerHTML;
        var a = window.open('', '', 'height=850, width=900');
        a.document.write('<html><head><title>چاپ سند #{doc_number}</title></head><body style="direction:rtl; font-family: B Nazanin, Tahoma; margin:0; padding:10px;">');
        a.document.write(divContents);
        a.document.write('</body></html>');
        a.document.close();
        a.focus();
        setTimeout(function(){{ a.print(); }}, 300);
    }}
    </script>
    """
    return full_html

# ==========================================
# ۵. صفحه ورود (Login) با کلید Enter فعال
# ==========================================
if not st.session_state.logged_in:
    c_l, c_c, c_r = st.columns([1, 1.3, 1])
    with c_c:
        st.markdown("""
        <div class="login-box">
            <h2 style="text-align:center;">🔐 ورود به سیستم مدیریت گدام</h2>
            <p style="text-align:center; opacity:0.8;">نام کاربری و رمز عبور را وارد کرده و Enter بزنید</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            u_in = st.text_input("نام کاربری:")
            p_in = st.text_input("رمز عبور:", type="password")
            if st.form_submit_button("ورود به برنامه", use_container_width=True):
                c = conn.cursor()
                c.execute("SELECT value FROM settings WHERE key='admin_user'")
                db_user = c.fetchone()[0]
                c.execute("SELECT value FROM settings WHERE key='admin_pass'")
                db_pass = c.fetchone()[0]

                if u_in == db_user and p_in == db_pass:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("❌ نام کاربری یا رمز عبور نادرست است!")
    st.stop()

# ==========================================
# ۶. منوی کناری (سایدبار)
# ==========================================
with st.sidebar:
    st.markdown("## 🏢 سیستم امانات گدام")
    st.caption(f"📅 تاریخ امروز: {get_shamsi_today()}")

    mode_lbl = "☀️ تغییر به حالت روز" if st.session_state.dark_mode else "🌙 تغییر به حالت شب (Dark)"
    if st.button(mode_lbl, use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

    st.divider()
    menu = st.radio(
        "منوی اصلی:",
        [
            "📊 داشبورد و آمار منطقه‌ای",
            "🤝 ثبت امانت جدید (سبد چند کالایی)",
            "↩️ ثبت برگشت یا مفقودی کالا",
            "👤 کارنامه اختصاصی هر نماینده",
            "🖨️ آرشیو، ویرایش و چاپ اسناد",
            "📦 مدیریت موجودی گدام",
            "👥 مدیریت نمایندگان",
            "⚙️ تنظیمات و تاریخچه تغییرات"
        ]
    )
    st.divider()

    if os.path.exists(DB_FILE):
        with open(DB_FILE, "rb") as f:
            st.download_button(
                "💾 دانلود نسخه پشتیبان (Backup)",
                data=f,
                file_name=f"Backup_Godam_{get_shamsi_today().replace('/','-')}.db",
                use_container_width=True
            )

    if st.button("🚪 خروج از سیستم", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# ==========================================
# صفحه ۱: داشبورد و گزارش‌گیری منطقه‌ای
# ==========================================
if menu == "📊 داشبورد و آمار منطقه‌ای":
    st.markdown("## داشبورد جامع گدام و توزیع منطقه‌ای")

    df_items = pd.read_sql_query("SELECT * FROM items", conn)
    df_reps = pd.read_sql_query("SELECT * FROM representatives", conn)
    df_loan_items = pd.read_sql_query("""
        SELECT li.id, ld.doc_number, ld.loan_date, r.name AS rep_name, r.area,
               i.name AS item_name, li.quantity, li.returned_qty, li.lost_qty,
               (li.quantity - li.returned_qty - li.lost_qty) AS active_qty
        FROM loan_items li
        JOIN loan_docs ld ON li.doc_id = ld.doc_id
        JOIN representatives r ON ld.rep_id = r.id
        JOIN items i ON li.item_id = i.id
    """, conn)

    total_stock = int(df_items['stock'].sum()) if not df_items.empty else 0
    total_active = int(df_loan_items['active_qty'].sum()) if not df_loan_items.empty else 0
    total_lost = int(df_loan_items['lost_qty'].sum()) if not df_loan_items.empty else 0
    active_reps = len(df_reps[df_reps['status'] == 'فعال']) if not df_reps.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="metric-card"><div class="metric-title">🏬 موجودی فعلی گدام</div><div class="metric-value">{total_stock:,} عدد</div><span class="metric-badge badge-blue">آماده تحویل</span></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card"><div class="metric-title">🤝 امانات فعال نزد نمایندگان</div><div class="metric-value">{total_active:,} عدد</div><span class="metric-badge badge-purple">در گردش</span></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card"><div class="metric-title">👥 نمایندگان فعال</div><div class="metric-value">{active_reps} از {len(df_reps)} نفر</div><span class="metric-badge badge-green">فعال در ساحه</span></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="metric-card"><div class="metric-title">⚠️ اقلام مفقودی / جریمه</div><div class="metric-value">{total_lost:,} عدد</div><span class="metric-badge badge-red">کسر شده از آمار</span></div>""", unsafe_allow_html=True)

    st.write("")
    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown("### 📦 مقایسه موجودی گدام و امانات نزد نمایندگان")
        if not df_items.empty:
            summary_rows = []
            for _, it in df_items.iterrows():
                in_field = int(df_loan_items[df_loan_items['item_name'] == it['name']]['active_qty'].sum()) if not df_loan_items.empty else 0
                summary_rows.append({"نوع جنس": it['name'], "موجودی گدام": it['stock'], "نزد نمایندگان": in_field, "کل اموال": it['stock'] + in_field})
            df_sum = pd.DataFrame(summary_rows)
            fig_bar = px.bar(df_sum, x="نوع جنس", y=["موجودی گدام", "نزد نمایندگان"], barmode="group", template=chart_template)
            st.plotly_chart(fig_bar, use_container_width=True)

    with ch2:
        st.markdown("### 🗺️ توزیع تجهیزات فعال به تفکیک ولسوالی / ساحه")
        if not df_loan_items.empty and total_active > 0:
            area_df = df_loan_items[df_loan_items['active_qty'] > 0].groupby(['area', 'item_name'])['active_qty'].sum().reset_index()
            fig_area = px.bar(area_df, x="area", y="active_qty", color="item_name", labels={"area": "ساحه / ولسوالی", "active_qty": "تعداد فعال", "item_name": "نوع جنس"}, template=chart_template)
            st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.info("هنوز تجهیزات فعالی در ساحات توزیع نشده است.")

    st.markdown("### 📋 خلاصه وضعیت کل اموال شرکت")
    if not df_items.empty:
        st.dataframe(df_sum, use_container_width=True, hide_index=True)

# ==========================================
# صفحه ۲: ثبت امانت جدید (سبد چند کالایی)
# ==========================================
elif menu == "🤝 ثبت امانت جدید (سبد چند کالایی)":
    st.markdown("## ثبت سند امانت جدید (امکان انتخاب چند جنس در یک سند)")

    reps = pd.read_sql_query("SELECT * FROM representatives WHERE status='فعال'", conn)
    items = pd.read_sql_query("SELECT * FROM items WHERE stock > 0", conn)

    if reps.empty or items.empty:
        st.warning("⚠️ برای ثبت امانت، باید حداقل یک نماینده «فعال» و یک جنس «دارای موجودی» در سیستم وجود داشته باشد.")
    else:
        col_top1, col_top2, col_top3 = st.columns(3)
        with col_top1:
            rep_opts = {f"{r['name']} ({r['area']})": r for _, r in reps.iterrows()}
            sel_rep_lbl = st.selectbox("۱. انتخاب نماینده فعال:", list(rep_opts.keys()))
            sel_rep = rep_opts[sel_rep_lbl]
        with col_top2:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM loan_docs")
            next_num = 1011 + c.fetchone()[0]
            doc_num = st.text_input("۲. شماره سند:", value=str(next_num))
        with col_top3:
            loan_date = st.text_input("۳. تاریخ صدور (هجری شمسی):", value=get_shamsi_today())

        st.divider()
        st.markdown("### ➕ افزودن اقلام به سبد این سند")

        # فرم افزودن هر قلم جنس به لیست سبد (با کلید Enter فعال)
        with st.form("add_to_cart_form", clear_on_submit=True):
            c_it1, c_it2, c_it3 = st.columns([2, 1, 1])
            with c_it1:
                item_opts = {f"[{r['code']}] {r['name']} — موجودی گدام: {r['stock']}": r for _, r in items.iterrows()}
                sel_it_lbl = st.selectbox("انتخاب جنس:", list(item_opts.keys()))
                sel_it = item_opts[sel_it_lbl]
            with c_it2:
                # محاسبه تعداد از قبل اضافه شده در سبد برای جلوگیری از عبور از موجودی گدام
                already_in_cart = sum(x['qty'] for x in st.session_state.cart if x['item_id'] == sel_it['id'])
                max_avail = int(sel_it['stock']) - already_in_cart
                qty_in = st.number_input("تعداد تحویلی:", min_value=1, max_value=max(1, max_avail), value=1)
            with c_it3:
                st.write("")
                st.write("")
                add_cart_btn = st.form_submit_button("⬇️ افزودن به لیست سند", use_container_width=True)

            if add_cart_btn:
                if max_avail <= 0:
                    st.error("❌ موجودی این جنس در گدام برای افزودن بیشتر کافی نیست!")
                else:
                    # اگر جنس قبلاً در سبد بود تعدادش جمع شود
                    found = False
                    for entry in st.session_state.cart:
                        if entry['item_id'] == sel_it['id']:
                            entry['qty'] += qty_in
                            found = True
                            break
                    if not found:
                        st.session_state.cart.append({
                            "item_id": int(sel_it['id']),
                            "code": sel_it['code'],
                            "name": sel_it['name'],
                            "qty": int(qty_in)
                        })
                    st.rerun()

        # نمایش سبد فعلی و دکمه ثبت نهایی
        if st.session_state.cart:
            st.markdown("#### 🛒 اقلام انتخاب شده برای این سند:")
            cart_df = pd.DataFrame(st.session_state.cart).rename(columns={"code": "کد جنس", "name": "نام جنس", "qty": "تعداد"})
            st.dataframe(cart_df[["کد جنس", "نام جنس", "تعداد"]], use_container_width=True, hide_index=True)

            c_btn1, c_btn2 = st.columns([1, 3])
            with c_btn1:
                if st.button("🗑️ خالی کردن لیست", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()

            notes = st.text_input("ملاحظات / توضیحات سند (اختیاری):", placeholder="مثلاً: تحویل جهت شروع فصل کاری")

            if st.button("✅ ثبت نهایی سند در دیتابیس و آماده‌سازی چاپ A5 دوتایی", type="primary", use_container_width=True):
                c = conn.cursor()
                c.execute("INSERT INTO loan_docs (doc_number, rep_id, loan_date, notes) VALUES (?, ?, ?, ?)",
                          (doc_num.strip(), int(sel_rep['id']), loan_date.strip(), notes.strip()))
                new_doc_id = c.lastrowid

                items_summary_log = []
                for item_entry in st.session_state.cart:
                    c.execute("INSERT INTO loan_items (doc_id, item_id, quantity, returned_qty, lost_qty) VALUES (?, ?, ?, 0, 0)",
                              (new_doc_id, item_entry['item_id'], item_entry['qty']))
                    c.execute("UPDATE items SET stock = stock - ? WHERE id = ?", (item_entry['qty'], item_entry['item_id']))
                    items_summary_log.append(f"{item_entry['name']} ({item_entry['qty']})")

                conn.commit()
                log_action("ثبت سند امانت", f"سند #{doc_num} به نام {sel_rep['name']} شامل: {', '.join(items_summary_log)}")

                saved_cart = list(st.session_state.cart)
                st.session_state.cart = []

                st.success(f"🎉 سند شماره #{doc_num} با موفقیت ثبت شد و موجودی گدام کسر گردید!")
                html_doc = generate_dual_a5_print_html(doc_num, loan_date, sel_rep['name'], sel_rep['phone'], sel_rep['area'], saved_cart, notes)
                components.html(html_doc, height=920, scrolling=True)

# ==========================================
# صفحه ۳: ثبت برگشت سالم یا مفقودی کالا
# ==========================================
elif menu == "↩️ ثبت برگشت یا مفقودی کالا":
    st.markdown("## ثبت بازگشت امانات به گدام یا ثبت مفقودی / خسارت")

    active_items = pd.read_sql_query("""
        SELECT li.id AS loan_item_id, ld.doc_number, ld.loan_date, r.name AS rep_name, r.area,
               i.id AS item_id, i.name AS item_name, li.quantity, li.returned_qty, li.lost_qty,
               (li.quantity - li.returned_qty - li.lost_qty) AS remaining
        FROM loan_items li
        JOIN loan_docs ld ON li.doc_id = ld.doc_id
        JOIN representatives r ON ld.rep_id = r.id
        JOIN items i ON li.item_id = i.id
        WHERE (li.quantity - li.returned_qty - li.lost_qty) > 0
        ORDER BY ld.doc_id DESC
    """, conn)

    if active_items.empty:
        st.info("🎉 هیچ جنس امانتی تسویه نشده‌ای نزد نمایندگان باقی نمانده است.")
    else:
        opts = {
            f"سند #{r['doc_number']} | نماینده: {r['rep_name']} | جنس: {r['item_name']} (باقی‌مانده نزد نماینده: {r['remaining']} عدد)": r
            for _, r in active_items.iterrows()
        }
        sel_lbl = st.selectbox("انتخاب ردیف امانت جهت تسویه:", list(opts.keys()))
        row = opts[sel_lbl]

        # نمایش شفاف مشخصات جنسی که نماینده تسلیم می‌دهد
        st.info(f"📌 **مشخصات تحویلی:** نماینده **«{row['rep_name']}»** از ساحه **{row['area']}** بابت سند **#{row['doc_number']}** موظف به تحویل **{row['remaining']} عدد «{row['item_name']}»** می‌باشد.")

        with st.form("return_or_lost_form"):
            c1, c2 = st.columns(2)
            with c1:
                op_type = st.radio("نوع عملیات تسویه:", ["↩️ برگشت سالم به گدام (افزایش موجودی انبار)", "⚠️ ثبت مفقودی / خسارت (جریمه - بدون اضافه شدن به گدام)"])
            with c2:
                qty_op = st.number_input("تعداد:", min_value=1, max_value=int(row['remaining']), value=int(row['remaining']))

            if st.form_submit_button("✅ ثبت نهایی عملیات (Enter)", use_container_width=True):
                c = conn.cursor()
                if "برگشت سالم" in op_type:
                    c.execute("UPDATE loan_items SET returned_qty = returned_qty + ? WHERE id = ?", (int(qty_op), int(row['loan_item_id'])))
                    c.execute("UPDATE items SET stock = stock + ? WHERE id = ?", (int(qty_op), int(row['item_id'])))
                    log_action("برگشت امانت", f"برگشت {qty_op} عدد {row['item_name']} از {row['rep_name']} (سند #{row['doc_number']})")
                    st.success(f"✅ تعداد {qty_op} عدد «{row['item_name']}» سالم به گدام بازگشت و موجودی انبار افزایش یافت.")
                else:
                    c.execute("UPDATE loan_items SET lost_qty = lost_qty + ? WHERE id = ?", (int(qty_op), int(row['loan_item_id'])))
                    log_action("ثبت مفقودی/جریمه", f"مفقودی {qty_op} عدد {row['item_name']} نزد {row['rep_name']} (سند #{row['doc_number']})")
                    st.warning(f"⚠️ تعداد {qty_op} عدد «{row['item_name']}» به عنوان مفقودی/خسارت ثبت شد و از حساب امانات نماینده کسر گردید.")
                conn.commit()
                st.rerun()

# ==========================================
# صفحه ۴: کارنامه اختصاصی هر نماینده
# ==========================================
elif menu == "👤 کارنامه اختصاصی هر نماینده":
    st.markdown("## صورت‌حساب و کارنامه تجهیزات هر نماینده")

    reps = pd.read_sql_query("SELECT * FROM representatives", conn)
    if reps.empty:
        st.info("نماینده‌ای ثبت نشده است.")
    else:
        rep_map = {f"{r['name']} — {r['area']} ({r['status']})": r for _, r in reps.iterrows()}
        sel_r_lbl = st.selectbox("نام نماینده را انتخاب کنید:", list(rep_map.keys()))
        rep = rep_map[sel_r_lbl]

        st.markdown(f"""
        <div class="metric-card">
            <h4>👤 مشخصات: {rep['name']} | 📱 موبایل: {rep['phone']} | 📍 ساحه: {rep['area']} | وضعیت: {rep['status']}</h4>
        </div>
        """, unsafe_allow_html=True)

        rep_loans = pd.read_sql_query("""
            SELECT ld.doc_number AS 'شماره سند', ld.loan_date AS 'تاریخ', i.name AS 'نوع جنس',
                   li.quantity AS 'تحویل گرفته', li.returned_qty AS 'برگشت داده', li.lost_qty AS 'مفقودی/جریمه',
                   (li.quantity - li.returned_qty - li.lost_qty) AS 'باقی‌مانده نزد نماینده'
            FROM loan_items li
            JOIN loan_docs ld ON li.doc_id = ld.doc_id
            JOIN items i ON li.item_id = i.id
            WHERE ld.rep_id = ?
            ORDER BY ld.doc_id DESC
        """, conn, params=(int(rep['id']),))

        if rep_loans.empty:
            st.info("تاکنون هیچ جنسی به این نماینده امانت داده نشده است.")
        else:
            st.markdown("### 📊 خلاصه تجهیزات فعلی نزد این نماینده")
            summary_rep = rep_loans.groupby("نوع جنس")[["تحویل گرفته", "برگشت داده", "مفقودی/جریمه", "باقی‌مانده نزد نماینده"]].sum().reset_index()
            st.dataframe(summary_rep, use_container_width=True, hide_index=True)

            st.markdown("### 📜 ریز تمام اسناد و حواله‌های این نماینده")
            st.dataframe(rep_loans, use_container_width=True, hide_index=True)

            csv_rep = rep_loans.to_csv(index=False).encode('utf-8-sig')
            st.download_button(f"📥 دانلود کارنامه {rep['name']} (Excel / CSV)", csv_rep, f"Karnameh_{rep['name']}.csv", "text/csv")

# ==========================================
# صفحه ۵: آرشیو، ویرایش و چاپ مجدد اسناد
# ==========================================
elif menu == "🖨️ آرشیو، ویرایش و چاپ اسناد":
    st.markdown("## آرشیو اسناد، چاپ مجدد و اصلاح اشتباهات")

    docs = pd.read_sql_query("""
        SELECT ld.doc_id, ld.doc_number, ld.loan_date, ld.notes, ld.rep_id,
               r.name AS rep_name, r.phone, r.area
        FROM loan_docs ld
        JOIN representatives r ON ld.rep_id = r.id
        ORDER BY ld.doc_id DESC
    """, conn)

    if docs.empty:
        st.info("هنوز سندی ثبت نشده است.")
    else:
        doc_opts = {f"سند #{r['doc_number']} | نماینده: {r['rep_name']} | تاریخ: {r['loan_date']}": r for _, r in docs.iterrows()}
        sel_doc_lbl = st.selectbox("انتخاب سند:", list(doc_opts.keys()))
        doc = doc_opts[sel_doc_lbl]

        doc_items_df = pd.read_sql_query("""
            SELECT li.id AS li_id, li.item_id, i.name, li.quantity, li.returned_qty, li.lost_qty
            FROM loan_items li
            JOIN items i ON li.item_id = i.id
            WHERE li.doc_id = ?
        """, conn, params=(int(doc['doc_id']),))

        tab_print, tab_edit = st.tabs(["🖨️ مشاهده و چاپ مجدد (A5 دوتایی)", "✏️ ویرایش یا حذف سند اشتباه"])

        with tab_print:
            items_for_print = [{"name": r['name'], "qty": r['quantity']} for _, r in doc_items_df.iterrows()]
            html_out = generate_dual_a5_print_html(doc['doc_number'], doc['loan_date'], doc['rep_name'], doc['phone'], doc['area'], items_for_print, doc['notes'])
            components.html(html_out, height=920, scrolling=True)

        with tab_edit:
            st.warning("⚠️ در صورت تغییر تعداد یا حذف سند، موجودی گدام به صورت خودکار اصلاح می‌شود.")
            all_reps = pd.read_sql_query("SELECT * FROM representatives", conn)

            with st.form("edit_doc_header_form"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_doc_num = st.text_input("شماره سند:", value=doc['doc_number'])
                with c2:
                    rep_names_list = list(all_reps['name'])
                    curr_idx = rep_names_list.index(doc['rep_name']) if doc['rep_name'] in rep_names_list else 0
                    new_rep_name = st.selectbox("تغییر نماینده:", rep_names_list, index=curr_idx)
                with c3:
                    new_date = st.text_input("تاریخ سند:", value=doc['loan_date'])
                new_notes = st.text_input("ملاحظات:", value=doc['notes'] if doc['notes'] else "")

                if st.form_submit_button("💾 ذخیره تغییرات سربرگ سند"):
                    new_rep_id = int(all_reps[all_reps['name'] == new_rep_name].iloc[0]['id'])
                    c = conn.cursor()
                    c.execute("UPDATE loan_docs SET doc_number=?, rep_id=?, loan_date=?, notes=? WHERE doc_id=?",
                              (new_doc_num, new_rep_id, new_date, new_notes, int(doc['doc_id'])))
                    conn.commit()
                    log_action("ویرایش سند", f"سند #{new_doc_num} ویرایش شد")
                    st.success("✅ تغییرات سند ذخیره شد.")
                    st.rerun()

            st.markdown("#### اصلاح تعداد اقلام این سند:")
            for _, l_row in doc_items_df.iterrows():
                with st.form(f"edit_item_{l_row['li_id']}"):
                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    with col_a:
                        st.write(f"**جنس:** {l_row['name']} (تعداد فعلی در سند: {l_row['quantity']})")
                    with col_b:
                        min_allowed = max(1, int(l_row['returned_qty']) + int(l_row['lost_qty']))
                        updated_qty = st.number_input("تعداد جدید:", min_value=min_allowed, value=int(l_row['quantity']), key=f"q_{l_row['li_id']}")
                    with col_c:
                        if st.form_submit_button("به‌روزرسانی تعداد"):
                            diff = int(updated_qty) - int(l_row['quantity'])
                            c = conn.cursor()
                            c.execute("SELECT stock FROM items WHERE id=?", (int(l_row['item_id']),))
                            avail_stock = c.fetchone()[0]
                            if diff > avail_stock:
                                st.error("❌ موجودی گدام برای افزایش این تعداد کافی نیست!")
                            else:
                                c.execute("UPDATE loan_items SET quantity=? WHERE id=?", (int(updated_qty), int(l_row['li_id'])))
                                c.execute("UPDATE items SET stock = stock - ? WHERE id=?", (diff, int(l_row['item_id'])))
                                conn.commit()
                                log_action("اصلاح تعداد سند", f"تعداد {l_row['name']} در سند #{doc['doc_number']} به {updated_qty} تغییر یافت")
                                st.success("✅ تعداد اصلاح و موجودی گدام تنظیم شد.")
                                st.rerun()

            st.divider()
            if st.button("🗑️ حذف کامل این سند و بازگرداندن تمام اجناس به گدام", type="primary"):
                c = conn.cursor()
                for _, l_row in doc_items_df.iterrows():
                    unreturned = int(l_row['quantity']) - int(l_row['returned_qty']) - int(l_row['lost_qty'])
                    if unreturned > 0:
                        c.execute("UPDATE items SET stock = stock + ? WHERE id=?", (unreturned, int(l_row['item_id'])))
                c.execute("DELETE FROM loan_items WHERE doc_id=?", (int(doc['doc_id']),))
                c.execute("DELETE FROM loan_docs WHERE doc_id=?", (int(doc['doc_id']),))
                conn.commit()
                log_action("حذف سند", f"سند #{doc['doc_number']} حذف و اجناس به گدام برگشت داده شد")
                st.success("✅ سند به طور کامل حذف شد.")
                st.rerun()

# ==========================================
# صفحه ۶: مدیریت موجودی گدام (بدون تکرار جنس)
# ==========================================
elif menu == "📦 مدیریت موجودی گدام":
    st.markdown("## مدیریت موجودی و اجناس گدام")

    col1, col2 = st.columns([1, 1.3])
    with col1:
        tab_add_stock, tab_new_item, tab_edit_item = st.tabs(["➕ افزایش موجودی اجناس", "🆕 تعریف جنس جدید", "✏️ ویرایش جنس"])

        df_all_items = pd.read_sql_query("SELECT * FROM items", conn)

        with tab_add_stock:
            st.caption("برای جلوگیری از ثبت جنس تکراری، جنس را از لیست زیر انتخاب کنید:")
            if not df_all_items.empty:
                with st.form("add_stock_form", clear_on_submit=True):
                    it_map = {f"[{r['code']}] {r['name']} (موجودی فعلی: {r['stock']})": r for _, r in df_all_items.iterrows()}
                    sel_it_k = st.selectbox("انتخاب جنس:", list(it_map.keys()))
                    add_qty = st.number_input("تعداد ورود جدید به گدام:", min_value=1, value=5)
                    if st.form_submit_button("✅ افزودن به موجودی گدام (Enter)", use_container_width=True):
                        target = it_map[sel_it_k]
                        c = conn.cursor()
                        c.execute("UPDATE items SET stock = stock + ? WHERE id=?", (int(add_qty), int(target['id'])))
                        conn.commit()
                        log_action("ورود به گدام", f"{add_qty} عدد به موجودی {target['name']} اضافه شد")
                        st.success(f"✅ {add_qty} عدد به «{target['name']}» اضافه شد.")
                        st.rerun()

        with tab_new_item:
            with st.form("create_new_item_form", clear_on_submit=True):
                n_code = st.text_input("کد جنس (مثلاً K-106):")
                n_name = st.text_input("نام جنس کاملاً جدید:")
                n_stock = st.number_input("موجودی اولیه:", min_value=0, value=10)
                if st.form_submit_button("ثبت جنس جدید (Enter)", use_container_width=True):
                    if n_name.strip():
                        try:
                            c = conn.cursor()
                            c.execute("INSERT INTO items (code, name, stock) VALUES (?, ?, ?)", (n_code.strip(), n_name.strip(), int(n_stock)))
                            conn.commit()
                            log_action("تعریف جنس جدید", f"جنس {n_name} با کد {n_code} ثبت شد")
                            st.success(f"✅ جنس جدید «{n_name}» ثبت شد.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("❌ این نام جنس قبلاً در گدام ثبت شده است! از تب «افزایش موجودی» استفاده کنید.")

        with tab_edit_item:
            if not df_all_items.empty:
                it_edit_map = {f"[{r['code']}] {r['name']}": r for _, r in df_all_items.iterrows()}
                sel_ed_k = st.selectbox("جنس جهت اصلاح:", list(it_edit_map.keys()))
                ed_row = it_edit_map[sel_ed_k]
                with st.form("edit_item_master_form"):
                    ed_code = st.text_input("کد جنس:", value=ed_row['code'])
                    ed_name = st.text_input("نام جنس:", value=ed_row['name'])
                    ed_stock = st.number_input("اصلاح موجودی فعلی گدام:", min_value=0, value=int(ed_row['stock']))
                    if st.form_submit_button("💾 ذخیره اصلاحات", use_container_width=True):
                        c = conn.cursor()
                        c.execute("UPDATE items SET code=?, name=?, stock=? WHERE id=?", (ed_code.strip(), ed_name.strip(), int(ed_stock), int(ed_row['id'])))
                        conn.commit()
                        log_action("ویرایش جنس گدام", f"مشخصات {ed_name} ویرایش شد")
                        st.success("✅ اطلاعات جنس اصلاح شد.")
                        st.rerun()

    with col2:
        st.markdown("### 📋 موجودی لحظه‌ای گدام")
        df_show_items = pd.read_sql_query("SELECT code AS 'کد جنس', name AS 'نام جنس', stock AS 'موجودی فعلی گدام' FROM items", conn)
        st.dataframe(df_show_items, use_container_width=True, hide_index=True)

# ==========================================
# صفحه ۷: مدیریت نمایندگان (افزودن، ویرایش، تغییر وضعیت)
# ==========================================
elif menu == "👥 مدیریت نمایندگان":
    st.markdown("## مدیریت نمایندگان و ساحات فعالیت")

    col1, col2 = st.columns([1, 1.4])
    with col1:
        t_add_r, t_edit_r = st.tabs(["➕ ثبت نماینده جدید", "✏️ ویرایش و تغییر وضعیت"])

        with t_add_r:
            with st.form("new_rep_form", clear_on_submit=True):
                r_name = st.text_input("نام و تخلص نماینده:")
                r_phone = st.text_input("شماره موبایل:")
                r_area = st.text_input("ساحه / ولسوالی:")
                r_status = st.selectbox("وضعیت:", ["فعال", "غیرفعال"])
                r_notes = st.text_input("یادداشت:")
                if st.form_submit_button("✅ ثبت نماینده (Enter)", use_container_width=True):
                    if r_name.strip():
                        c = conn.cursor()
                        c.execute("INSERT INTO representatives (name, phone, area, status, notes) VALUES (?, ?, ?, ?, ?)",
                                  (r_name.strip(), r_phone.strip(), r_area.strip(), r_status, r_notes.strip()))
                        conn.commit()
                        log_action("ثبت نماینده", f"نماینده {r_name} در {r_area} ثبت شد")
                        st.success(f"✅ نماینده «{r_name}» ثبت شد.")
                        st.rerun()

        with t_edit_r:
            all_r = pd.read_sql_query("SELECT * FROM representatives", conn)
            if not all_r.empty:
                r_map = {f"{r['id']} - {r['name']} ({r['status']})": r for _, r in all_r.iterrows()}
                sel_rk = st.selectbox("انتخاب نماینده:", list(r_map.keys()))
                rr = r_map[sel_rk]
                with st.form("edit_rep_form"):
                    en = st.text_input("نام نماینده:", value=rr['name'])
                    ep = st.text_input("شماره موبایل:", value=rr['phone'] if rr['phone'] else "")
                    ea = st.text_input("ساحه / ولسوالی:", value=rr['area'] if rr['area'] else "")
                    es = st.selectbox("وضعیت فعالیت:", ["فعال", "غیرفعال"], index=0 if rr['status'] == "فعال" else 1)
                    enote = st.text_input("یادداشت:", value=rr['notes'] if rr['notes'] else "")
                    if st.form_submit_button("💾 ذخیره تغییرات نماینده", use_container_width=True):
                        c = conn.cursor()
                        c.execute("UPDATE representatives SET name=?, phone=?, area=?, status=?, notes=? WHERE id=?",
                                  (en.strip(), ep.strip(), ea.strip(), es, enote.strip(), int(rr['id'])))
                        conn.commit()
                        log_action("ویرایش نماینده", f"مشخصات {en} به وضعیت {es} تغییر یافت")
                        st.success("✅ اطلاعات نماینده به‌روزرسانی شد.")
                        st.rerun()

    with col2:
        st.markdown("### 📋 لیست کل نمایندگان")
        filter_st = st.radio("فیلتر نمایش:", ["همه", "فعال", "غیرفعال"], horizontal=True)
        q = "SELECT id AS 'کد', name AS 'نام نماینده', phone AS 'موبایل', area AS 'ولسوالی / ساحه', status AS 'وضعیت', notes AS 'یادداشت' FROM representatives"
        if filter_st != "همه":
            q += f" WHERE status='{filter_st}'"
        df_r_show = pd.read_sql_query(q, conn)
        st.dataframe(df_r_show, use_container_width=True, hide_index=True)

# ==========================================
# صفحه ۸: تنظیمات رمز عبور و تاریخچه تغییرات (Logs)
# ==========================================
elif menu == "⚙️ تنظیمات و تاریخچه تغییرات":
    st.markdown("## تنظیمات امنیتی و گزارش تاریخچه عملیات")

    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown("### 🔐 تغییر نام کاربری و رمز عبور")
        with st.form("change_pass_form"):
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='admin_user'")
            cur_u = c.fetchone()[0]
            new_u = st.text_input("نام کاربری جدید:", value=cur_u)
            new_p = st.text_input("رمز عبور جدید:", type="password")
            if st.form_submit_button("تغییر رمز ورود", use_container_width=True):
                if new_u.strip() and new_p.strip():
                    c.execute("UPDATE settings SET value=? WHERE key='admin_user'", (new_u.strip(),))
                    c.execute("UPDATE settings SET value=? WHERE key='admin_pass'", (new_p.strip(),))
                    conn.commit()
                    log_action("تغییر رمز", "رمز عبور مدیریت تغییر یافت")
                    st.success("✅ نام کاربری و رمز عبور با موفقیت تغییر کرد.")
                else:
                    st.error("لطفاً هر دو فیلد را پر کنید.")

    with c2:
        st.markdown("### 🕵️ تاریخچه ثبت و ویرایش‌های سیستم (Audit Log)")
        df_logs = pd.read_sql_query("SELECT action_time AS 'زمان', action_type AS 'نوع عملیات', details AS 'جزئیات' FROM audit_logs ORDER BY id DESC LIMIT 100", conn)
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
