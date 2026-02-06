import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統 (穩定版)")

# --- 2. 快取功能 ---
@st.cache_data(ttl=3600)
def get_stock_base_info(symbol):
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        try:
            hist = ticker.history(period="5d")
            if not hist.empty:
                info = ticker.info
                name = info.get('shortName', info.get('longName', f"股票 {symbol}"))
                return f"{symbol}{suffix}", name
        except:
            continue
    return None, None

# --- 3. 檔案管理區 ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
    ])

# 儲存計算結果的狀態
if 'calc_results' not in st.session_state:
    st.session_state.calc_results = None

st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])
if uploaded_file:
    df_input = pd.read_csv(uploaded_file)
    df_input['買進日期'] = pd.to_datetime(df_input['買進日期']).dt.date
    st.session_state.df = df_input

# --- 4. 編輯與下載 ---
st.subheader("📝 庫存清單編輯")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)
csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 下載目前庫存 CSV", data=csv_data, file_name="my_portfolio.csv", mime="text/csv")

# --- 5. 計算按鈕 ---
if st.button("🚀 執行完整分析"):
    results = []
    t_inv, t_val, t_div = 0, 0, 0
    all_actions_data = []

    with st.spinner('同步數據中...'):
        for _, row in edited_df.iterrows():
            sid = str(row['代碼']).strip()
            full_id, s_name = get_stock_base_info(sid)
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                cur_p = hist['Close'].iloc[-1]
                buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                actions = ticker.actions
                c_div, f_sh = 0, row['持有股數']
                my_act = pd.DataFrame()
                if not actions.empty:
                    actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                    my_act = actions.loc[buy_dt:]
                    c_div = (my_act['Dividends'] * row['持有股數']).sum()
                    for split in my_act['Stock Splits']:
                        if split > 0: f_sh *= split
                inv_c = (row['買進單價'] * row['持有股數']) * 1.00085 
                cur_v = cur_p * f_sh
                results.append({
                    "名稱": s_name, "代碼": sid, "目前股價": round(cur_p, 2), "持有股數": int(f_sh),
                    "累積股息": int(c_div), "總損益": int((cur_v+c_div)-inv_c), 
                    "報酬率%": round(((cur_v+c_div)-inv_c)/inv_c*100, 2), "市值": int(cur_v)
                })
                if not my_act.empty: all_actions_data.append({"name": s_name, "sid": sid, "data": my_act})
                t_inv, t_val, t_div = t_inv + inv_c, t_val + cur_v, t_div + c_div

        # 將結果存入 session_state
        st.session_state.calc_results = {
            "res_df": pd.DataFrame(results),
            "summary": (t_inv, t_val, t_div),
            "actions": all_actions_data
        }

# --- 6. 顯示結果 (這部分移出 button 區塊，確保刷新時不會消失) ---
if st.session_state.calc_results:
    data = st.session_state.calc_results
    res_df = data["res_df"]
    t_inv, t_val, t_div = data["summary"]

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總投入成本", f"{int(t_inv):,}")
    c2.metric("目前總市值", f"{int(t_val):,}")
    c3.metric("累積領息", f"{int(t_div):,}")
    net_p = (t_val + t_div) - t_inv
    net_r = (net_p / t_inv) * 100 if t_inv > 0 else 0
    st.session_state.net_p = net_p # 存下來備用
    c4.metric("總淨損益", f"{int(net_p):,}", f"{net_r:.2f}%", delta_color="inverse" if net_p >= 0 else "normal")

    col_l, col_r = st.columns(2)
    with col_l:
        st.write("### 🍕 資產比例")
        st.plotly_chart(px.pie(res_df, values='市值', names='名稱', hole=0.4), use_container_width=True)
    with col_r:
        st.write("### 📊 獲利比較")
        res_df['顏色'] = res_df['總損益'].apply(lambda x: '獲利' if x >= 0 else '虧損')
        st.plotly_chart(px.bar(res_df, x='名稱', y='總損益', color='顏色', color_discrete_map={'獲利': '#ef553b', '虧損': '#00cc96'}), use_container_width=True)

    st.dataframe(res_df.drop(columns=['顏色']), use_container_width=True)

    # --- 關鍵修正：走勢圖獨立顯示區 ---
    st.write("---")
    st.subheader("📈 個別標的分析")
    target_name = st.selectbox("選擇股票：", res_df['名稱'].tolist())
    target_info = res_df[res_df['名稱'] == target_name].iloc[0]
    t_sid = target_info['代碼']
    
    # 重新獲取該股票的原始買價
    orig_row = edited_df[edited_df['代碼'].astype(str) == str(t_sid)].iloc[0]
    buy_p = orig_row['買進單價']

    p_map = {"一日": "1d", "一週": "5d", "一月": "1mo", "一年": "1y", "五年": "5y"}
    sel_p = st.radio("範圍：", list(p_map.keys()), horizontal=True, index=2)
    
    # 繪製趨勢圖
    t_obj = yf.Ticker(f"{t_sid}.TW" if not "." in str(t_sid) else t_sid)
    h_data = t_obj.history(period=p_map[sel_p])
    if not h_data.empty:
        fig = px.line(h_data, x=h_data.index, y='Close', title=f"{target_name} 走勢")
        fig.add_hline(y=buy_p, line_dash="dash", line_color="orange", annotation_text=f"買入價: {buy_p}")
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("🔍 歷史除權息明細"):
        for item in data["actions"]:
            st.write(f"**📍 {item['name']}**")
            df_disp = item['data'].copy()
            df_disp.index = df_disp.index.date
            df_disp = df_disp.rename(columns={"Dividends": "現金股利", "Stock Splits": "配股比"})
            st.table(df_disp[(df_disp != 0).any(axis=1)])