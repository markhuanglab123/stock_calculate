import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統 (終極完整版)")

# --- 2. 快取功能：加速抓取名稱與上市櫃判斷 ---
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

# --- 3. 側邊欄：檔案管理 ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

if uploaded_file is not None:
    try:
        df_input = pd.read_csv(uploaded_file)
        df_input['買進日期'] = pd.to_datetime(df_input['買進日期']).dt.date
        st.session_state.df = df_input
    except Exception as e:
        st.sidebar.error(f"檔案格式錯誤: {e}")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
        {"代碼": "0050", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 120.0, "持有股數": 1000},
    ])

# --- 4. 編輯介面 ---
st.subheader("📝 庫存清單編輯")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 下載目前庫存 CSV 備份", data=csv_data, file_name="my_portfolio.csv", mime="text/csv")

# --- 5. 執行計算 ---
if st.button("🚀 執行完整損益與走勢分析"):
    results = []
    t_inv, t_val, t_div = 0, 0, 0
    all_actions_data = []

    with st.spinner('正在同步市場數據中...'):
        for _, row in edited_df.iterrows():
            sid = str(row['代碼']).strip()
            full_id, s_name = get_stock_base_info(sid)
            
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                
                cur_p = hist['Close'].iloc[-1]
                buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                
                # 除權息計算
                actions = ticker.actions
                c_div, f_sh = 0, row['持有股數']
                my_actions = pd.DataFrame()
                
                if not actions.empty:
                    actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                    my_actions = actions.loc[buy_dt:]
                    c_div = (my_actions['Dividends'] * row['持有股數']).sum()
                    for split in my_actions['Stock Splits']:
                        if split > 0: f_sh *= split

                inv_c = (row['買進單價'] * row['持有股數']) * 1.00085 
                cur_v = cur_p * f_sh
                prof = (cur_v + c_div) - inv_c
                roi = (prof / inv_c) * 100

                results.append({
                    "名稱": s_name, "代碼": sid, "目前股價": round(cur_p, 2), "持有股數": int(f_sh),
                    "累積股息": int(c_div), "總損益": int(prof), "報酬率%": round(roi, 2), "市值": int(cur_v)
                })
                
                if not my_actions.empty:
                    all_actions_data.append({"name": s_name, "sid": sid, "data": my_actions})

                t_inv += inv_c
                t_val += cur_v
                t_div += c_div

    if results:
        res_df = pd.DataFrame(results)
        
        # --- 顯示總計指標 ---
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總投入成本", f"{int(t_inv):,}")
        c2.metric("目前總市值", f"{int(t_val):,}")
        c3.metric("總累計領息", f"{int(t_div):,}")
        
        net_p = (t_val + t_div) - t_inv
        net_r = (net_p / t_inv) * 100 if t_inv > 0 else 0
        p_color = "inverse" if net_p >= 0 else "normal"
        c4.metric("帳戶總淨損益", f"{int(net_p):,}", f"{net_r:.2f}%", delta_color=p_color)

        # --- 視覺化圖表 ---
        st.write("---")
        col_left, col_right = st.columns(2)
        with col_left:
            st.write("### 🍕 資產配置比例")
            fig_pie = px.pie(res_df, values='市值', names='名稱', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_right:
            st.write("### 📊 獲利比較")
            res_df['顏色'] = res_df['總損益'].apply(lambda x: '獲利' if x >= 0 else '虧損')
            fig_bar = px.bar(res_df, x='名稱', y='總損益', color='顏色', color_discrete_map={'獲利': '#ef553b', '虧損': '#00cc96'})
            st.plotly_chart(fig_bar, use_container_width=True)

        st.write("### 📋 持股明細報表")
        st.dataframe(res_df.drop(columns=['顏色']), use_container_width=True)

        # --- 個別標的動態走勢圖 (新增功能) ---
        st.write("---")
        st.subheader("📈 個別標的動態分析 (含買入價標示)")
        target_name = st.selectbox("選擇要分析的股票：", res_df['名稱'].tolist())
        target_info = res_df[res_df['名稱'] == target_name].iloc[0]
        t_sid = target_info['代碼']
        
        # 抓取原始買價
        orig_row = edited_df[edited_df['代碼'].astype(str) == str(t_sid)].iloc[0]
        buy_p = orig_row['買進單價']
        
        period_map = {"一日": "1d", "一週": "5d", "一月": "1mo", "一年": "1y", "五年": "5y"}
        sel_period = st.radio("時間範圍：", list(period_map.keys()), horizontal=True, index=2)
        
        t_obj = yf.Ticker(f"{t_sid}.TW" if not "." in str(t_sid) else t_sid)
        h_data = t_obj.history(period=period_map[sel_period])
        
        if not h_data.empty:
            fig_trend = px.line(h_data, x=h_data.index, y='Close', title=f"{target_name} ({t_sid}) 走勢與成本線")
            fig_trend.add_hline(y=buy_p, line_dash="dash", line_color="orange", annotation_text=f"買入價: {buy_p}")
            st.plotly_chart(fig_trend, use_container_width=True)

        # --- 除權息歷史紀錄 ---
        with st.expander("🔍 點擊查看歷史除權息明細"):
            if all_actions_data:
                for item in all_actions_data:
                    st.write(f"**📍 {item['name']} ({item['sid']})**")
                    df_disp = item['data'].copy()
                    df_disp.index = df_disp.index.date
                    df_disp = df_disp.rename(columns={"Dividends": "現金股利", "Stock Splits": "配股/拆分比"})
                    df_disp = df_disp[(df_disp != 0).any(axis=1)]
                    if not df_disp.empty: st.table(df_disp)
                    else: st.write("此區間內無除權息紀錄。")
    else:
        st.error("請確認清單中的代碼是否正確。")