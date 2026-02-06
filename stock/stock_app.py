import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import time

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="⚡", layout="wide")
st.title("⚡ 台股資產管理系統 (極速效能版)")

# --- 2. 核心功能：極速名稱對照 (離線優先) ---
@st.cache_data(ttl=86400) # 快取 24 小時
def get_stock_name_offline(symbol):
    """優先使用內建字典，找不到才連網"""
    symbol = str(symbol).strip()
    if symbol.isdigit() and len(symbol) < 4:
        symbol = symbol.zfill(4)
    
    # 【內建前 50+ 熱門股與 ETF，大幅減少連網需求】
    common_db = {
        "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2303": "聯電", "2308": "台達電",
        "2881": "富邦金", "2882": "國泰金", "2891": "中信金", "2886": "兆豐金", "2884": "玉山金",
        "1101": "台泥", "1102": "亞泥", "1216": "統一", "1301": "台塑", "1303": "南亞",
        "1326": "台化", "2002": "中鋼", "2105": "正新", "2207": "和泰車", "2327": "國巨",
        "2357": "華碩", "2382": "廣達", "2395": "研華", "2412": "中華電", "2603": "長榮",
        "2609": "陽明", "2615": "萬海", "2912": "統一超", "3008": "大立光", "3034": "聯詠",
        "3037": "欣興", "3045": "台灣大", "3231": "緯創", "3711": "日月光投控", "4904": "遠傳",
        "4938": "和碩", "5871": "中租-KY", "5876": "上海商銀", "5880": "合庫金", "6505": "台塑化",
        "6669": "緯穎", "9910": "豐泰", "0050": "元大台灣50", "0056": "元大高股息", "00878": "國泰永續高股息",
        "00929": "復華台灣科技優息", "00940": "元大台灣價值高息", "00919": "群益台灣精選高息", "0052": "富邦科技",
        "006208": "富邦台50", "00713": "元大台灣高息低波", "2340": "台亞", "2408": "南亞科"
    }
    
    # 1. 查表 (0 秒延遲)
    if symbol in common_db:
        return f"{symbol}.TW", common_db[symbol], symbol
    
    # 2. 只有表裡沒有的才去連網 (較慢)
    for suffix in [".TW", ".TWO"]:
        try:
            ticker = yf.Ticker(f"{symbol}{suffix}")
            # 使用 fast_info 避免過度讀取
            if ticker.fast_info.currency == 'TWD':
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
    st.session_state.df['代碼'] = st.session_state.df['代碼'].astype(str)

# --- 4. 側邊欄：檔案管理 (含進度條) ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

if uploaded_file:
    # 讀取 CSV
    try:
        raw_df = pd.read_csv(uploaded_file)
        raw_df.columns = [c.strip() for c in raw_df.columns] # 清洗欄位空白
        if "股票名稱" not in raw_df.columns: raw_df["股票名稱"] = ""
        
        # 檢查是否需要更新
        # 簡單判定：如果行數不同，或第一行的代碼不同，就視為新檔案
        # (為了效能，不進行全表深度比對)
        current_rows = len(st.session_state.df)
        new_rows = len(raw_df)
        
        # 只有當使用者上傳新檔案時才處理，避免 Streamlit 迴圈
        if st.session_state.get('last_uploaded') != uploaded_file.name:
            
            progress_bar = st.sidebar.progress(0)
            status_text = st.sidebar.empty()
            processed_rows = []
            
            total = len(raw_df)
            for i, (_, row) in enumerate(raw_df.iterrows()):
                # 更新進度條
                status_text.text(f"正在處理第 {i+1}/{total} 筆資料...")
                progress_bar.progress((i + 1) / total)
                
                sid = str(row['代碼']).strip()
                orig_name = str(row.get('股票名稱', '')).strip()
                
                # 如果 CSV 裡沒名字，才去查
                if not orig_name or orig_name == "nan":
                    _, name, fixed_sid = get_stock_name_offline(sid)
                    final_name = name if name else "未知"
                else:
                    fixed_sid = sid.zfill(4) if sid.isdigit() and len(sid)<4 else sid
                    final_name = orig_name

                processed_rows.append({
                    "代碼": fixed_sid,
                    "股票名稱": final_name,
                    "買進日期": pd.to_datetime(row['買進日期']).date(),
                    "買進單價": float(row['買進單價']),
                    "持有股數": int(row['持有股數'])
                })
            
            st.session_state.df = pd.DataFrame(processed_rows)
            st.session_state.last_uploaded = uploaded_file.name # 標記已處理過
            st.session_state.calc_results = None
            
            status_text.text("✅ 匯入完成！")
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
            st.rerun()

    except Exception as e:
        st.sidebar.error(f"匯入錯誤: {e}")

if st.sidebar.button("🗑️ 清除所有資料"):
    st.session_state.df = pd.DataFrame(columns=["代碼", "股票名稱", "買進日期", "買進單價", "持有股數"])
    st.session_state.calc_results = None
    if 'last_uploaded' in st.session_state: del st.session_state['last_uploaded']
    st.rerun()

# --- 5. 編輯介面 ---
st.subheader("📝 庫存清單編輯")
st.info("💡 提示：輸入代碼並按下 Enter，分析時會自動校正名稱。")

# 這裡移除自動觸發的 rerun 邏輯，改為「分析時統一校正」，確保編輯時極度滑順
edited_df = st.data_editor(
    st.session_state.df, 
    num_rows="dynamic", 
    use_container_width=True,
    key="editor_main"
)

# 匯出 CSV
csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 匯出目前清單 (CSV)", data=csv_data, file_name="my_portfolio.csv", mime="text/csv")

# --- 6. 執行分析 (含多執行緒加速概念) ---
if st.button("🚀 執行完整分析"):
    process_df = edited_df.copy()
    
    # 1. 先校正一次名稱 (針對手動新增的行)
    with st.spinner('正在校對股票代碼與名稱...'):
        for idx, row in process_df.iterrows():
            sid = str(row['代碼']).strip()
            c_name = str(row['股票名稱']).strip()
            if sid and (not c_name or c_name == "nan" or c_name == "None"):
                 _, name, fixed_sid = get_stock_name_offline(sid)
                 if name:
                     process_df.at[idx, '股票名稱'] = name
                     process_df.at[idx, '代碼'] = fixed_sid
    
    # 更新回 session 以便顯示修正後的表格
    st.session_state.df = process_df
    
    # 2. 開始計算損益
    results, t_inv, t_val, t_div = [], 0, 0, 0
    unique_ids = [str(sid) for sid in process_df['代碼'].unique() if sid and str(sid) != "None"]
    
    with st.spinner(f'正在分析 {len(unique_ids)} 支標的...'):
        for sid in unique_ids:
            full_id, s_name, fixed_sid = get_stock_name_offline(sid)
            if not full_id: continue # 找不到就跳過
            
            # 抓取該股的所有買入紀錄
            mask = process_df['代碼'] == fixed_sid
            stock_group = process_df[mask]
            
            ticker = yf.Ticker(full_id)
            hist = ticker.history(period="5d")
            
            if hist.empty:
                # 容錯：如果真的抓不到，用買入價當現價 (避免崩潰)
                cur_p = stock_group['買進單價'].iloc[0]
            else:
                cur_p = hist['Close'].iloc[-1]
            
            sub_sh, sub_cost, sub_div = 0, 0, 0
            
            # 計算該股票的總體數據
            actions = ticker.actions # 這是最耗時的步驟
            
            for _, row in stock_group.iterrows():
                buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                row_sh, row_div = row['持有股數'], 0
                
                if not actions.empty:
                    # 簡單過濾
                    my_act = actions[actions.index >= buy_dt]
                    if not my_act.empty:
                        row_div = (my_act['Dividends'] * row['持有股數']).sum()
                        for split in my_act['Stock Splits']:
                            if split > 0: row_sh *= split
                            
                sub_cost += (row['買進單價'] * row['持有股數']) * 1.00085
                sub_sh += row_sh
                sub_div += row_div
            
            cur_v = cur_p * sub_sh
            roi = ((cur_v+sub_div)-sub_cost)/sub_cost*100 if sub_cost > 0 else 0
            
            results.append({
                "名稱": s_name, "代碼": fixed_sid, "目前股價": round(cur_p, 2), "持有股數": int(sub_sh),
                "累積股息": int(sub_div), "總損益": int((cur_v+sub_div)-sub_cost), 
                "報酬率%": round(roi, 2), "市值": int(cur_v), "平均成本": round(sub_cost/sub_sh, 2)
            })
            t_inv += sub_cost; t_val += cur_v; t_div += sub_div

        st.session_state.calc_results = {
            "res_df": pd.DataFrame(results), 
            "summary": (t_inv, t_val, t_div), 
            "raw_records": process_df 
        }

# --- 7. 結果呈現 ---
if 'calc_results' in st.session_state and st.session_state.calc_results:
    res = st.session_state.calc_results
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總投入", f"{int(res['summary'][0]):,}")
    c2.metric("目前市值", f"{int(res['summary'][1]):,}")
    c3.metric("總領息", f"{int(res['summary'][2]):,}")
    net = (res['summary'][1] + res['summary'][2]) - res['summary'][0]
    # 防呆：避免分母為0
    roi_total = (net/res['summary'][0]*100) if res['summary'][0] > 0 else 0
    st.metric("總淨損益", f"{int(net):,}", f"{roi_total:.2f}%", delta_color="inverse" if net >= 0 else "normal")

    st.write("### 📊 庫存匯總報告")
    st.dataframe(res['res_df'], use_container_width=True)

    st.write("---")
    st.subheader("📈 個別標的深度分析")
    
    opt = [f"{r['代碼']} - {r['名稱']}" for _, r in res['res_df'].iterrows()]
    if opt:
        sel = st.selectbox("選擇股票：", opt)
        sel_sid = sel.split(" - ")[0]
        p_map = {"一日": "1d", "一週": "5d", "一月": "1mo", "一年": "1y", "五年": "5y"}
        sel_p = st.radio("選擇時間範圍：", list(p_map.keys()), horizontal=True, index=3)

        # 準備繪圖
        raw_records = res['raw_records']
        my_buys = raw_records[raw_records['代碼'] == sel_sid]
        avg_price = res['res_df'][res['res_df']['代碼'] == sel_sid].iloc[0]['平均成本']
        
        full_id, _, _ = get_stock_name_offline(sel_sid)
        t_obj = yf.Ticker(full_id)
        h_data = t_obj.history(period=p_map[sel_p])
        
        if not h_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], mode='lines', name='股價'))
            fig.add_hline(y=avg_price, line_dash="dash", line_color="orange", annotation_text=f"平均成本:{avg_price}")
            
            h_min, h_max = h_data.index.min().date(), h_data.index.max().date()
            for _, buy_row in my_buys.iterrows():
                b_date = buy_row['買進日期']
                if h_min <= b_date <= h_max:
                    b_dt_ts = pd.to_datetime(b_date)
                    fig.add_trace(go.Scatter(x=[b_dt_ts, b_dt_ts], y=[h_data['Close'].min(), h_data['Close'].max()],
                                             mode="lines", line=dict(color="red", width=1, dash="dot"), showlegend=False))
                    fig.add_annotation(x=b_dt_ts, y=buy_row['買進單價'], text=f"買:{int(buy_row['買進單價'])}", 
                                       showarrow=True, arrowhead=2, arrowcolor="red")
            
            fig.update_layout(title=f"{sel} - {sel_p} 走勢圖", height=500)
            st.plotly_chart(fig, use_container_width=True)