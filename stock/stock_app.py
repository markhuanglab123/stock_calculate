# --- 1. 自動判斷上市上櫃並抓取名稱 ---
def get_ticker_data(symbol):
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        # 抓取最近 5 天資料確認代碼存在
        hist = ticker.history(period="5d")
        if not hist.empty:
            # 優先抓取 shortName，如果沒有則用代碼代替
            stock_name = ticker.info.get('shortName', f"股票 {symbol}")
            return ticker, f"{symbol}{suffix}", hist, stock_name
    return None, None, None, None

# ... (中間編輯與 CSV 邏輯保持不變) ...

# --- 4. 計算與顯示邏輯修正 ---
if st.button("🚀 開始計算總損益"):
    results = []
    t_inv, t_val, t_div = 0, 0, 0

    with st.spinner('正在獲取股票名稱與市價...'):
        for _, row in edited_df.iterrows():
            sid = str(row['代碼'])
            ticker, full_id, hist, s_name = get_ticker_data(sid) # 多接收一個名稱
            
            if ticker:
                cur_price = hist['Close'].iloc[-1]
                # ... (中間除權息計算保持不變) ...

                results.append({
                    "股票名稱": s_name,  # 新增這一欄
                    "代碼": full_id,
                    "目前股價": round(cur_price, 2),
                    "持有股數": int(final_sh),
                    "累計股息": int(cash_div),
                    "總損益": int(profit),
                    "報酬率%": round(roi, 2)
                })
                # ... (加總邏輯保持不變) ...

    # --- 5. 呈現結果 ---
    # (顯示 Metric 卡片...)
    
    st.write("### 📈 個別標的詳細報告")
    # 將結果轉換為 DataFrame 並顯示，股票名稱會出現在第一欄
    st.dataframe(pd.DataFrame(results), use_container_width=True)