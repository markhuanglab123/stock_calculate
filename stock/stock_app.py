import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統 (完整功能版)")

# --- 2. 核心功能：名稱對照、補零 ---
@st.cache_data(ttl=3600)
def get_stock_base_info(symbol):
    # 強制轉字串並補零
    symbol = str(symbol).strip()
    if symbol.isdigit() and len(symbol) < 4:
        symbol = symbol.zfill(4)
    
    # 手動維護常見中文名稱 (解決 yfinance 只有英文的問題)
    common_names = {
        "2330": "台積電", "0050": "元大台灣50", "0052": "富邦科技",
        "0056": "元大高股息", "2317": "鴻海", "2454": "聯發科",
        "2303": "聯電", "2340": "台亞", "2408": "南亞科",
        "2881": "富邦金", "2882": "國泰金", "00878": "國泰永續高股息",
        "2603": "長榮", "2609": "陽明", "2615": "萬海", "3231": "緯創"
    }
    
    if symbol in common_names:
        return f"{symbol}.TW", common_names[symbol], symbol
        
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        try:
            # 嘗試抓取
            if ticker.fast_info:
                info = ticker.info
                name = info.get('longName') or info.get('shortName') or f"股票 {symbol}"
                return f"{symbol}{suffix}", name, symbol
        except:
            continue
    return None, None, symbol

# --- 3. 初始化 Session State ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "股票名稱": "台積電", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
    ])

# --- 4. 側邊欄：檔案管理 ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

if uploaded_file:
    try:
        raw_df = pd.read_csv(uploaded_file)
        raw_df.columns = [c.strip() for c in raw_df.columns]
        
        processed_rows = []
        for _, row in raw_df.iterrows():
            sid = str(row['代碼']).strip()
            _, name, fixed_sid = get_stock_base_info(sid)
            processed_rows.append({
                "代碼": fixed_sid,
                "股票名稱": name if name else "未知",
                "買進日期": pd.to_datetime(row['買進日期']).date(),
                "買進單價": float(row['買進單價']),
                "持有股數": int(row['持有股數'])
            })
        
        new_df = pd.DataFrame(processed_rows)
        # 避免重複刷新
        if not new_df.equals(st.session_state.df):
            st.session_state.df = new_df
            st.session_state.calc_results = None # 清除舊結果
            st.rerun()
            
    except Exception as e:
        st.sidebar.error(f"匯入失敗：{e}")

if st.sidebar.button("🗑️ 清除所有資料"):
    st.session_state.df = pd.DataFrame(columns=["代碼", "股票名稱", "買進日期", "買進單價", "持有股數"])
    st.session_state.calc_results = None
    st.rerun()

# --- 5. 編輯介面 ---
st.subheader("📝 庫存清單編輯")
edited_df = st.data_editor(
    st.session_state.df, 
    num_rows="dynamic", 
    use_container_width=True,
    key="portfolio_editor"
)

# --- 6. 執行分析 ---
if st.button("🚀 執行完整分析"):
    temp_df = edited_df.copy()
    results, t_inv, t_val, t_div = [], 0, 0, 0
    
    # 抓取所有不重複代碼 (需補零)
    unique_ids = [str(sid).strip().zfill(4) if str(sid).strip().isdigit() else str(sid).strip() 
                  for sid in temp_df['代碼'].unique() if sid and str(sid) != "None"]

    with st.spinner('正在同步市場數據...'):
        for sid in unique_ids:
            full_id, s_name, fixed_sid = get_stock_base_info(sid)
            # 篩選出該代碼的所有交易紀錄
            stock_group = temp_df[temp_df['代碼'].astype(str).str.strip().apply(lambda x: x.zfill(4) if x.isdigit() else x) == fixed_sid]
            
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                cur_p = hist['Close'].iloc[-1]
                
                sub_sh, sub_cost, sub_div = 0, 0, 0
                for _, row in stock_group.iterrows():
                    buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                    actions = ticker.actions
                    row_sh, row_div = row['持有股數'], 0
                    
                    if not actions.empty:
                        actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                        my_act = actions.loc[buy_dt:]
                        row_div = (my_act['Dividends'] * row['持有股數']).sum()
                        for split in my_act['Stock Splits']:
                            if split > 0: row_sh *= split
                            
                    sub_cost += (row['買進單價'] * row['持有股數']) * 1.00085
                    sub_sh += row_sh
                    sub_div += row_div
                
                cur_v = cur_p * sub_sh
                results.append({
                    "名稱": s_name, "代碼": fixed_sid, "目前股價": round(cur_p, 2), "持有股數": int(sub_sh),
                    "累積股息": int(sub_div), "總損益": int((cur_v+sub_div)-sub_cost), 
                    "報酬率%": round(((cur_v+sub_div)-sub_cost)/sub_cost*100, 2) if sub_cost > 0 else 0,
                    "市值": int(cur_v), "平均成本": round(sub_cost/sub_sh, 2)
                })
                t_inv, t_val, t_div = t_inv + sub_cost, t_val + cur_v, t_div + sub_div

        st.session_state.calc_results = {
            "res_df": pd.DataFrame(results), 
            "summary": (t_inv, t_val, t_div), 
            "raw_records": temp_df # 存下來給線圖用
        }

# --- 7. 結果顯示與線圖區 ---
if 'calc_results' in st.session_state and st.session_state.calc_results:
    res = st.session_state.calc_results
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總投入", f"{int(res['summary'][0]):,}")
    c2.metric("目前市值", f"{int(res['summary'][1]):,}")
    c3.metric("總領息", f"{int(res['summary'][2]):,}")
    net = (res['summary'][1] + res['summary'][2]) - res['summary'][0]
    st.metric("總淨損益", f"{int(net):,}", f"{(net/res['summary'][0]*100):.2f}%", delta_color="inverse" if net >= 0 else "normal")

    st.write("### 📊 庫存匯總報告")
    st.dataframe(res['res_df'], use_container_width=True)

    # --- 8. 修正回來的：個股深度分析 (含時間切換) ---
    st.write("---")
    st.subheader("📈 個別標的深度分析")
    
    # 下拉選單
    opt = [f"{r['代碼']} - {r['名稱']}" for _, r in res['res_df'].iterrows()]
    sel = st.selectbox("選擇股票：", opt)
    sel_sid = sel.split(" - ")[0]
    
    # 這裡就是你要的「選擇時間範圍」功能！
    p_map = {"一日": "1d", "一週": "5d", "一月": "1mo", "一年": "1y", "五年": "5y"}
    sel_p = st.radio("選擇時間範圍：", list(p_map.keys()), horizontal=True, index=3) # 預設一年

    # 準備繪圖數據
    raw_records = res['raw_records']
    # 確保格式一致 (轉字串、去空白、補零)
    raw_records['代碼_清標'] = raw_records['代碼'].astype(str).str.strip().apply(lambda x: x.zfill(4) if x.isdigit() else x)
    my_buys = raw_records[raw_records['代碼_清標'] == sel_sid]
    
    avg_price = res['res_df'][res['res_df']['代碼'] == sel_sid].iloc[0]['平均成本']
    
    # 抓取歷史股價
    t_obj = yf.Ticker(f"{sel_sid}.TW" if not "." in str(sel_sid) else sel_sid)
    h_data = t_obj.history(period=p_map[sel_p])
    
    if not h_data.empty:
        fig = go.Figure()
        
        # 1. 股價線
        fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], mode='lines', name='股價'))
        
        # 2. 平均成本線 (橘色虛線)
        fig.add_hline(y=avg_price, line_dash="dash", line_color="orange", annotation_text=f"平均成本:{avg_price}")
        
        # 3. 買入點標記 (紅色垂直線)
        h_min, h_max = h_data.index.min().date(), h_data.index.max().date()
        
        for _, buy_row in my_buys.iterrows():
            b_date = buy_row['買進日期']
            # 只有當買入日期在目前選擇的時間範圍內才顯示
            if h_min <= b_date <= h_max:
                b_dt_ts = pd.to_datetime(b_date)
                
                # 畫垂直紅線
                fig.add_trace(go.Scatter(
                    x=[b_dt_ts, b_dt_ts], 
                    y=[h_data['Close'].min(), h_data['Close'].max()],
                    mode="lines", 
                    line=dict(color="red", width=1, dash="dot"), 
                    showlegend=False
                ))
                
                # 標註買入價格
                fig.add_annotation(
                    x=b_dt_ts, 
                    y=buy_row['買進單價'], 
                    text=f"買點:{buy_row['買進單價']}", 
                    showarrow=True, 
                    arrowhead=2, 
                    arrowcolor="red"
                )
        
        fig.update_layout(title=f"{sel} - {sel_p} 走勢圖", height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("無法取得此時間區間的股價資料。")