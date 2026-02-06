import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="💰", layout="wide")
st.title("💰 台股全功能資產儀表板")

# --- 2. 快取功能：加速抓取名稱與上市櫃判斷 ---
@st.cache_data(ttl=3600)
def get_stock_base_info(symbol):
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        try:
            # 測試抓取 5 天資料確認代碼存在
            hist = ticker.history(period="5d")
            if not hist.empty:
                info = ticker.info
                # 優先抓取中文名稱，若無則用英文名或代碼
                name = info.get('shortName', info.get('longName', f"股票 {symbol}"))
                return f"{symbol}{suffix}", name
        except:
            continue
    return None, None

# --- 3. 側邊欄：檔案管理 ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

# 初始化 Session State 中的資料表格
if uploaded_file is not None:
    try:
        df_input = pd.read_csv(uploaded_file)
        # 統一將買進日期轉為 date 物件以便編輯器顯示
        df_input['買進日期'] = pd.to_datetime(df_input['買進日期']).dt.date
        st.session_state.df = df_input
    except Exception as e:
        st.sidebar.error(f"檔案格式錯誤: {e}")

if 'df' not in st.session_state:
    # 預設範例資料
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
        {"代碼": "0050", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 120.0, "持有股數": 1000},
    ])

# --- 4. 編輯介面 ---
st.subheader("📝 庫存清單編輯")
# 讓使用者直接在網頁修改表格
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# 下載按鈕 (加上 utf-8-sig 確保 Excel 不亂碼)
csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 下載目前庫存 CSV 備份", data=csv_data, file_name="my_portfolio.csv", mime="text/csv")

# --- 5. 核心計算按鈕 ---
if st.button("🚀 執行完整損益分析"):
    results = []
    t_inv, t_val, t_div = 0, 0, 0
    all_actions_data = [] # 儲存用於明細顯示的資料

    with st.spinner('同步市場數據中，請稍候...'):
        for _, row in edited_df.iterrows():
            sid = str(row['代碼']).strip()
            full_id, s_name = get_stock_base_info(sid)
            
            if full_id:
                ticker = yf.Ticker(full_id)
                # 抓取最新股價
                hist = ticker.history(period="5d")
                if hist.empty: continue
                
                cur_p = hist['Close'].iloc[-1]
                buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                
                # 計算除權息與股數變化
                actions = ticker.actions
                c_div, f_sh = 0, row['持有股數']
                
                my_actions = pd.DataFrame() # 初始化該標的的明細
                
                if not actions.empty:
                    # 處理時區比較
                    actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                    my_actions = actions.loc[buy_dt:]
                    
                    # 加總股息
                    c_div = (my_actions['Dividends'] * row['持有股數']).sum()
                    # 計算配股後的最終股數
                    for split in my_actions['Stock Splits']:
                        if split > 0: f_sh *= split

                # 損益計算 (手續費估算)
                inv_c = (row['買進單價'] * row['持有股數']) * 1.00085 
                cur_v = cur_p * f_sh
                prof = (cur_v + c_div) - inv_c
                roi = (prof / inv_c) * 100

                # 存入結果表格
                results.append({
                    "名稱": s_name,
                    "代碼": sid,
                    "目前股價": round(cur_p, 2),
                    "持有股數": int(f_sh),
                    "累積股息": int(c_div),
                    "總損益": int(prof),
                    "報酬率%": round(roi, 2),
                    "市值": int(cur_v)
                })
                
                # 存入明細顯示用
                if not my_actions.empty:
                    all_actions_data.append({"name": s_name, "sid": sid, "data": my_actions})

                # 累加總帳戶數值
                t_inv += inv_c
                t_val += cur_v
                t_div += c_div
            else:
                st.warning(f"無法辨識代碼: {sid}")

    # --- 6. 視覺化呈現 ---
    if results:
        res_df = pd.DataFrame(results)
        
        # A. 總計數值卡片
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總投入成本", f"{int(t_inv):,}")
        c2.metric("目前總市值", f"{int(t_val):,}")
        c3.metric("總累計領息", f"{int(t_div):,}")
        
        net_p = (t_val + t_div) - t_inv
        net_r = (net_p / t_inv) * 100 if t_inv > 0 else 0
        # 台灣邏輯：獲利顯示紅色 (inverse)
        p_color = "inverse" if net_p >= 0 else "normal"
        c4.metric("帳戶總淨損益", f"{int(net_p):,}", f"{net_r:.2f}%", delta_color=p_color)

        # B. 圖表分析
        st.write("---")
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.write("### 🍕 資產比例配置")
            fig_pie = px.pie(res_df, values='市值', names='名稱', hole=0.4, 
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_right:
            st.write("### 📊 個別標度損益比較")
            res_df['顏色'] = res_df['總損益'].apply(lambda x: '獲利' if x >= 0 else '虧損')
            fig_bar = px.bar(res_df, x='名稱', y='總損益', color='顏色',
                             color_discrete_map={'獲利': '#ef553b', '虧損': '#00cc96'})
            st.plotly_chart(fig_bar, use_container_width=True)

        # C. 詳細報表
        st.write("### 📋 持股詳細報表")
        st.dataframe(res_df.drop(columns=['顏色']), use_container_width=True)

        # D. 股息明細 (Expander)
        st.write("---")
        with st.expander("🔍 點擊展開：查看各標的歷史除權息明細 (核對用)"):
            if all_actions_data:
                for item in all_actions_data:
                    st.write(f"**📍 {item['name']} ({item['sid']})**")
                    df_disp = item['data'].copy()
                    df_disp.index = df_disp.index.date
                    # 使用 rename 避免欄位不符錯誤
                    df_disp = df_disp.rename(columns={"Dividends": "現金股利", "Stock Splits": "配股/拆分比"})
                    # 只顯示非 0 的有效紀錄
                    df_disp = df_disp[(df_disp != 0).any(axis=1)]
                    if not df_disp.empty:
                        st.table(df_disp)
                    else:
                        st.write("此區間內無除權息紀錄。")
            else:
                st.write("選定區間內所有標的皆無除權息紀錄。")
    else:
        st.error("請在庫存清單中輸入正確的股票代碼。")