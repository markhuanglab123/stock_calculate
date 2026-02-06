import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import plotly.graph_objects as go

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統 (最強容錯版)")

# --- 2. 核心功能：抓取名稱與補零 ---
# --- 修正後的名稱抓取邏輯 ---
@st.cache_data(ttl=3600)
def get_stock_base_info(symbol):
    symbol = str(symbol).strip()
    if symbol.isdigit() and len(symbol) < 4:
        symbol = symbol.zfill(4)
        
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        try:
            # 優先嘗試抓取 info
            info = ticker.info
            
            # 台灣股票中文名通常存在 'longName' 或 'shortName'
            # 這裡我們加上一個邏輯：如果抓到的是純英文，則標註代碼
            name = info.get('longName') or info.get('shortName') or f"股票 {symbol}"
            
            # 部分標的在 yfinance 仍會回傳英文，這是資料源限制
            return f"{symbol}{suffix}", name, symbol
        except:
            continue
    return None, None, symbol

# --- 3. 初始化 Session State ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "股票名稱": "台積電", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
    ])

if 'calc_results' not in st.session_state:
    st.session_state.calc_results = None

# --- 4. 側邊欄檔案管理 (強化容錯) ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

if uploaded_file:
    try:
        df_new = pd.read_csv(uploaded_file)
        # 清洗欄位：去除空白並強制轉換
        df_new.columns = [c.strip() for c in df_new.columns]
        
        # 如果少了「股票名稱」欄位，自動補齊
        if "股票名稱" not in df_new.columns:
            df_new["股票名稱"] = "待讀取"
            
        # 處理每一列資料
        processed_rows = []
        for _, row in df_new.iterrows():
            sid = str(row['代碼']).strip().split('.')[0] # 去除 .TW 等後綴
            _, name, fixed_sid = get_stock_base_info(sid)
            
            processed_rows.append({
                "代碼": fixed_sid,
                "股票名稱": name if name else "未知",
                "買進日期": pd.to_datetime(row['買進日期']).date(),
                "買進單價": float(row['買進單價']),
                "持有股數": int(row['持有股數'])
            })
        
        new_df = pd.DataFrame(processed_rows)
        # 檢查是否真的有變動才觸發 rerun
        if not new_df.equals(st.session_state.df):
            st.session_state.df = new_df
            st.session_state.calc_results = None
            st.rerun()
            
    except Exception as e:
        st.sidebar.error(f"匯入失敗！請檢查 CSV 欄位。錯誤：{e}")

# --- 5. 編輯介面 ---
st.subheader("📝 庫存清單編輯")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# 下載範例 (幫助使用者對齊格式)
sample_csv = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 下載目前資料 CSV", data=sample_csv, file_name="my_portfolio.csv", mime="text/csv")

# --- 6. 計算按鈕 ---
if st.button("🚀 執行完整分析"):
    process_df = edited_df.copy()
    results = []
    t_inv, t_val, t_div = 0, 0, 0
    
    # 過濾有效代碼
    ids_to_process = [str(sid).strip() for sid in process_df['代碼'].unique() if sid and str(sid) != "None"]

    with st.spinner(f'正在分析 {len(ids_to_process)} 支標的...'):
        for sid in ids_to_process:
            full_id, s_name, fixed_sid = get_stock_base_info(sid)
            # 聚合相同代碼的股票
            stock_group = process_df[process_df['代碼'].astype(str).str.strip().str.zfill(4) == fixed_sid]
            
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                cur_p = hist['Close'].iloc[-1]
                
                total_sh, total_cost, total_div = 0, 0, 0
                for _, row in stock_group.iterrows():
                    buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                    actions = ticker.actions
                    row_sh = row['持有股數']
                    row_div = 0
                    
                    if not actions.empty:
                        actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                        my_act = actions.loc[buy_dt:]
                        row_div = (my_act['Dividends'] * row['持有股數']).sum()
                        for split in my_act['Stock Splits']:
                            if split > 0: row_sh *= split
                    
                    total_cost += (row['買進單價'] * row['持有股數']) * 1.00085
                    total_sh += row_sh
                    total_div += row_div
                
                cur_v = cur_p * total_sh
                results.append({
                    "名稱": s_name, "代碼": fixed_sid, "目前股價": round(cur_p, 2), "持有股數": int(total_sh),
                    "累積股息": int(total_div), "總損益": int((cur_v+total_div)-total_cost), 
                    "報酬率%": round(((cur_v+total_div)-total_cost)/total_cost*100, 2) if total_cost > 0 else 0,
                    "市值": int(cur_v), "平均成本": round(total_cost/total_sh, 2)
                })
                t_inv, t_val, t_div = t_inv + total_cost, t_val + cur_v, t_div + total_div

        st.session_state.calc_results = {
            "res_df": pd.DataFrame(results),
            "summary": (t_inv, t_val, t_div),
            "raw_records": process_df
        }

# --- 7. 顯示結果與穩定線圖 ---
if st.session_state.calc_results:
    data = st.session_state.calc_results
    res_df = data["res_df"]
    raw_records = data["raw_records"]
    t_inv, t_val, t_div = data["summary"]

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總投入", f"{int(t_inv):,}")
    c2.metric("目前總市值", f"{int(t_val):,}")
    c3.metric("總領息", f"{int(t_div):,}")
    net_p = (t_val + t_div) - t_inv
    net_r = (net_p / t_inv) * 100 if t_inv > 0 else 0
    st.metric("總淨損益", f"{int(net_p):,}", f"{net_r:.2f}%", delta_color="inverse" if net_p >= 0 else "normal")

    st.write("### 📊 庫存匯總報告")
    st.dataframe(res_df, use_container_width=True)

    # --- 8. 多點標註走勢圖 ---
    st.write("---")
    st.subheader("📈 個別標的深度分析")
    option_list = [f"{row['代碼']} - {row['名稱']}" for _, row in res_df.iterrows()]
    selected_option = st.selectbox("選擇股票：", option_list)
    sel_sid = selected_option.split(" - ")[0]
    
    # 確保比對時代碼格式一致
    raw_records['代碼_清標'] = raw_records['代碼'].astype(str).str.strip().str.zfill(4)
    this_stock_buys = raw_records[raw_records['代碼_清標'] == sel_sid]
    avg_price = res_df[res_df['代碼'] == sel_sid].iloc[0]['平均成本']
    
    p_map = {"一日": "1d", "一週": "5d", "一月": "1mo", "一年": "1y", "五年": "5y"}
    sel_p = st.radio("範圍：", list(p_map.keys()), horizontal=True, index=3)
    
    t_obj = yf.Ticker(f"{sel_sid}.TW" if not "." in str(sel_sid) else sel_sid)
    h_data = t_obj.history(period=p_map[sel_p])
    
    if not h_data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], mode='lines', name='股價'))
        fig.add_hline(y=avg_price, line_dash="dash", line_color="orange", annotation_text=f"平均成本:{avg_price}")
        
        h_min, h_max = h_data.index.min().date(), h_data.index.max().date()
        for _, buy_row in this_stock_buys.iterrows():
            b_date = buy_row['買進日期']
            if h_min <= b_date <= h_max:
                b_dt_ts = pd.to_datetime(b_date)
                fig.add_trace(go.Scatter(
                    x=[b_dt_ts, b_dt_ts], y=[h_data['Close'].min(), h_data['Close'].max()],
                    mode="lines", line=dict(color="red", width=1, dash="dot"), showlegend=False
                ))
                fig.add_annotation(x=b_dt_ts, y=buy_row['買進單價'], text=f"買點:{buy_row['買進單價']}", showarrow=True, arrowhead=2, arrowcolor="red")
        
        st.plotly_chart(fig, use_container_width=True)