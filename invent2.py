import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import requests
import os
import time
import threading

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Sree Solutions", layout="wide", page_icon="🛍️")

# --- 2. THEME & BUTTON VISIBILITY FIX ---
st.markdown("""
<style>
    /* Main Background */
    [data-testid="stAppViewContainer"] { background-color: #050505; color: #ffffff; }
    
    /* SIDEBAR VISIBILITY */
    [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 1px solid #FFD700; }
    [data-testid="stSidebarNav"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { 
        color: #FFD700 !important; font-weight: bold !important; 
    }

    /* HEADINGS */
    h1, h2, h3 { color: #FFD700 !important; font-weight: bold !important; }
    
    /* INPUT BOXES */
    .stTextInput input, div[data-baseweb="select"] > div {
        background-color: #ffffff !important; color: #000000 !important; font-weight: bold !important;
    }

    /* BILL AMOUNT HIGHLIGHT */
    [data-testid="stMetricValue"] { color: #FFD700 !important; font-size: 3rem !important; font-weight: 800 !important; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 15px; border: 2px solid #FFD700; }

    /* SAVE BUTTON FIX - Making it Super Visible */
    .stButton>button { 
        background-color: #FFD700 !important; /* Bright Gold Background */
        color: #000000 !important;          /* Sharp Black Text */
        font-size: 1.2rem !important;
        font-weight: 900 !important;        /* Extra Bold */
        width: 100%; 
        border-radius: 10px; 
        height: 4em;
        border: 2px solid #ffffff !important; /* White border for extra pop */
        box-shadow: 0px 4px 15px rgba(255, 215, 0, 0.3);
    }
    .stButton>button:hover {
        background-color: #ffffff !important; /* Turns white on hover */
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE SETUP ---
def get_connection():
    return sqlite3.connect('sree_solutions_stable.db', check_same_thread=False)

def init_db():
    conn = get_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS master_stock 
                 (product TEXT PRIMARY KEY, mrp REAL, ap_price REAL, sap_price REAL, stock INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sales_history (
            date TEXT, customer_name TEXT, customer_phone TEXT, 
            product TEXT, qty INTEGER, mode TEXT, payment_mode TEXT, final_total REAL)''')
    conn.commit()
init_db()

# --- 4. TELEGRAM & SCHEDULER ---
def send_telegram(header, message):
    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": f"🔔 *{header}*\n\n{message}", "parse_mode": "Markdown"}, timeout=10)
    except: pass

def daily_scheduler():
    sent_today = False
    while True:
        now = datetime.now()
        if now.hour == 21 and now.minute == 0 and not sent_today:
            conn = get_connection()
            df = pd.read_sql("SELECT product, stock FROM master_stock", conn)
            if not df.empty:
                stock_list = "\n".join([f"• {r['product']}: {r['stock']}" for _, r in df.iterrows()])
                send_telegram("DAILY STOCK REPORT", f"📅 {now.strftime('%d-%m-%Y')}\n\n{stock_list}")
            sent_today = True
        if now.hour == 22: sent_today = False
        time.sleep(30)

if 'sch' not in st.session_state:
    threading.Thread(target=daily_scheduler, daemon=True).start()
    st.session_state.sch = True

# --- 5. SIDEBAR ---
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align: center;'>SREE SOLUTIONS</h2>", unsafe_allow_html=True)
    st.write("---")
    page = st.radio("CHOOSE SECTION", ["🏠 Billing", "⚙️ Inventory", "📊 History"])

# --- 6. BILLING ---
if page == "🏠 Billing":
    st.markdown("<h1>🧾 New Sale</h1>", unsafe_allow_html=True)
    if 'k' not in st.session_state: st.session_state.k = 0
    
    col1, col2, col3 = st.columns([1, 1, 0.8])
    with col1: cust_name = st.text_input("👤 Customer Name")
    with col2: cust_phone = st.text_input("📞 Phone Number")
    with col3: pay_mode = st.selectbox("💰 Payment Mode", ["Cash", "PhonePe", "GPay", "Credit"])
    
    conn = get_connection()
    df_stock = pd.read_sql("SELECT * FROM master_stock", conn)
    
    if not df_stock.empty:
        edited = st.data_editor(df_stock.assign(Qty=0, Price_Mode="MRP"), key=f"ed_{st.session_state.k}", use_container_width=True, hide_index=True)
        
        def calc_price(row):
            if row['Price_Mode'] == "AP": return row['ap_price']
            if row['Price_Mode'] == "SAP": return row['sap_price']
            return row['mrp']
        
        edited['Total'] = edited.apply(lambda r: calc_price(r) * r['Qty'], axis=1)
        sold = edited[edited['Qty'] > 0]
        
        if not sold.empty:
            g_total = sold['Total'].sum()
            st.metric("Total Bill Amount", f"₹ {g_total:,.2f}")
            # Ippudu ee button chala bright ga kanipisthundi
            if st.button("🚀 SAVE & SEND REPORT"):
                if not cust_name: st.error("Please enter Customer Name!")
                else:
                    d_now = datetime.now().strftime('%d-%m-%Y %H:%M')
                    items_msg = ""
                    for _, r in sold.iterrows():
                        items_msg += f"\n• {r['product']} ({int(r['Qty'])} x {r['Price_Mode']})"
                        conn.execute("UPDATE master_stock SET stock = stock - ? WHERE product = ?", (r['Qty'], r['product']))
                        conn.execute("INSERT INTO sales_history VALUES (?,?,?,?,?,?,?,?)", (d_now, cust_name, cust_phone, r['product'], r['Qty'], r['Price_Mode'], pay_mode, r['Total']))
                    conn.commit()
                    send_telegram("SALE DONE", f"👤 *Cust:* {cust_name}\n💰 *Total:* ₹{g_total:,.2f}\n💳 *Mode:* {pay_mode}\n📦 *Items:* {items_msg}")
                    st.success("Sale Recorded!")
                    st.session_state.k += 1; time.sleep(1); st.rerun()
    else:
        st.warning("Inventory empty! Add items in Inventory section.")

# --- 7. INVENTORY ---
elif page == "⚙️ Inventory":
    st.markdown("<h1>⚙️ Stock Update</h1>", unsafe_allow_html=True)
    data_input = st.text_area("Paste: Name MRP AP SAP Stock")
    if st.button("➕ UPDATE STOCK"):
        if data_input:
            conn = get_connection(); c = conn.cursor()
            for line in data_input.split('\n'):
                p = line.replace(',', ' ').split()
                if len(p) >= 5:
                    pname = " ".join(p[:-4]); m, a, s, q = p[-4], p[-3], p[-2], p[-1]
                    c.execute("INSERT OR REPLACE INTO master_stock VALUES (?,?,?,?,?)", (pname, m, a, s, q))
            conn.commit(); st.success("Stock Updated!")

# --- 8. HISTORY ---
else:
    st.markdown("<h1>📊 History</h1>", unsafe_allow_html=True)
    df_h = pd.read_sql("SELECT * FROM sales_history ORDER BY rowid DESC", get_connection())
    st.dataframe(df_h, use_container_width=True)