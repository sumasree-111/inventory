import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import requests
import os

# --- 1. GLOBAL CONFIGURATION & LUXURY THEME ---
st.set_page_config(page_title="Sree Solutions", layout="wide")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #050505; color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 1px solid #FFD700; }
    
    /* SIDEBAR TEXT & HEADINGS */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stWidgetLabel"] p { 
        color: #FFD700 !important; font-weight: bold !important; 
    }
    
    /* METRICS & DASHBOARD */
    [data-testid="stMetricValue"] { color: #FFD700 !important; font-weight: bold; }
    
    /* MODERN BUTTONS */
    .stButton>button { 
        background-color: #FFD700 !important; 
        color: #000000 !important; 
        font-weight: bold; 
        width: 100%; 
        border-radius: 10px; 
        height: 3em;
    }
    .stButton>button:hover { background-color: #ffffff !important; }

    /* TABLE HEADERS */
    div[data-testid="stTable"] th { color: #FFD700 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATABASE & WHATSAPP LOGIC ---
def get_connection():
    return sqlite3.connect('sree_business_v11.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS master_stock (product TEXT PRIMARY KEY, mrp REAL, ap_price REAL, sap_price REAL, stock INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sales_history (date TEXT, product TEXT, qty INTEGER, mode TEXT, final_total REAL)''')
    conn.commit()
init_db()

def send_silent_whatsapp(numbers, message):
    try:
        id_inst = st.secrets["GREEN_API_ID"]
        token_inst = st.secrets["GREEN_API_TOKEN"]
        for num in numbers:
            url = f"https://api.green-api.com/waInstance{id_inst}/sendMessage/{token_inst}"
            requests.post(url, json={"chatId": f"{str(num).strip()}@c.us", "message": message})
    except: pass

# --- 3. SIDEBAR WITH LOGO ---
# GitHub lo 'logo.png' unte adhi load avthundi, lekapothe emoji chupisthundi
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.markdown("<h1 style='text-align: center; color: #FFD700;'>🛍️</h1>", unsafe_allow_html=True)

st.sidebar.markdown("<h2 style='text-align: center; color: #FFD700; border: none;'>SREE SOLUTIONS</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

REPORT_NUMBERS = ["919493878186",] # Update this Sree
page = st.sidebar.radio("CHOOSE SECTION", ["🏠 Billing", "📊 Dashboard", "⚙️ Inventory", "📜 History"])

# --- 4. PAGES ---
if "🏠 Billing" in page:
    st.markdown("<h1 style='color: #FFD700;'>🧾 Live Billing</h1>", unsafe_allow_html=True)
    conn = get_connection()
    master_df = pd.read_sql("SELECT * FROM master_stock", conn)
    
    if not master_df.empty:
        search = st.text_input("🔍 Search Product...")
        filtered = master_df[master_df['product'].str.contains(search, case=False)] if search else master_df
        
        if 'rk' not in st.session_state: st.session_state.rk = 0
        edited = st.data_editor(filtered.assign(Qty=0, Mode="MRP"), key=f"b_{st.session_state.rk}", use_container_width=True, hide_index=True)
        
        def calc(row):
            p = row['ap_price'] if row['Mode']=="AP" else (row['sap_price'] if row['Mode']=="SAP" else row['mrp'])
            return p * row['Qty']
        
        edited['Total'] = edited.apply(calc, axis=1)
        sold = edited[edited['Qty'] > 0]

        if not sold.empty:
            bill_amt = sold['Total'].sum()
            st.metric("Total Amount", f"₹ {bill_amt:,.2f}")
            
            if st.button("💾 SAVE & REPORT"):
                valid = True
                for _, r in sold.iterrows():
                    if r['Qty'] > r['stock']:
                        st.error(f"❌ Low Stock: {r['product']}!"); valid = False; break
                
                if valid:
                    d = datetime.now().strftime('%Y-%m-%d')
                    d_show = datetime.now().strftime('%d-%m-%Y %H:%M')
                    
                    items_details = ""
                    for _, r in sold.iterrows():
                        items_details += f"\n• {r['product']} (Qty: {int(r['Qty'])})"
                    
                    for _, r in sold.iterrows():
                        conn.execute("UPDATE master_stock SET stock = stock - ? WHERE product = ?", (r['Qty'], r['product']))
                        conn.execute("INSERT INTO sales_history VALUES (?,?,?,?,?)", (d, r['product'], r['Qty'], r['Mode'], r['Total']))
                    conn.commit()
                    
                    report_msg = f"""
*SALE CONFIRMED - SREE SOLUTIONS*
-------------------------------
📅 *Date:* {d_show}
💰 *Total Sale:* ₹{bill_amt:,.2f}
📦 *Items Sold:* {items_details}
🔢 *Total Items Count:* {len(sold)}
✅ *Status:* Database Updated
-------------------------------
"""
                    send_silent_whatsapp(REPORT_NUMBERS, report_msg)
                    st.success("✅ Success! WhatsApp Report Sent.")
                    st.session_state.rk += 1
                    st.rerun()

elif "📊 Dashboard" in page:
    st.markdown("<h1 style='color: #FFD700;'>📊 Business Dashboard</h1>", unsafe_allow_html=True)
    s_df = pd.read_sql("SELECT * FROM sales_history", get_connection())
    st.metric("Revenue", f"₹ {s_df['final_total'].sum():,.2f}")
    if not s_df.empty: st.bar_chart(s_df.groupby('product')['final_total'].sum())

elif "⚙️ Inventory" in page:
    st.markdown("<h1 style='color: #FFD700;'>⚙️ Inventory Setup</h1>", unsafe_allow_html=True)
    txt = st.text_area("Format: Name, MRP, AP, SAP, Stock")
    if st.button("UPDATE MASTER DATA"):
        conn = get_connection(); c = conn.cursor()
        for l in txt.split('\n'):
            p = l.replace(',', ' ').split()
            if len(p) >= 5:
                c.execute("INSERT OR REPLACE INTO master_stock VALUES (?,?,?,?,?)", (" ".join(p[:-4]), p[-4], p[-3], p[-2], p[-1]))
        conn.commit(); st.success("Updated!")

else:
    st.markdown("<h1 style='color: #FFD700;'>📜 History</h1>", unsafe_allow_html=True)
    st.dataframe(pd.read_sql("SELECT * FROM sales_history ORDER BY date DESC", get_connection()), use_container_width=True)