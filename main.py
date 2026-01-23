import asyncio
import os
import time
import textwrap
from colorama import Fore, Style, init
import config
import database
import technical
import sentiment

init(autoreset=True)

async def run_analysis(symbol):
    print(f"{Fore.YELLOW}>> Memulai Analisa (Modules)...{Style.RESET_ALL}", end="\r")
    
    loop = asyncio.get_running_loop()
    
    # 1. Analisa Saham
    tech_data = await loop.run_in_executor(None, technical.get_technical_analysis, symbol)
    
    # 2. Analisa Pasar (Market Weather)
    market_data = await loop.run_in_executor(None, technical.get_market_overview)
    
    # 3. Analisa Berita (Jina)
    news_list = await loop.run_in_executor(None, sentiment.get_jina_news, symbol)
    
    print(f"{Fore.YELLOW}>> Mengirim ke Gemini AI...      {Style.RESET_ALL}", end="\r")
    ai_result = await sentiment.analyze_sentiment(news_list, symbol)
    
    return tech_data, ai_result, market_data

def print_kv(key, value, color=Fore.WHITE):
    print(f"{key:<18} : {color}{value}{Style.RESET_ALL}")

async def main():
    database.init_db()
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Fore.GREEN}=== AI TRADER PRO (STABLE V19) ==={Style.RESET_ALL}")
    
    symbol = "NVDA"
    print("-" * 50)
    
    print(f"{Fore.CYAN}--- STATUS POSISI KAMU ---{Style.RESET_ALL}")
    print("1. Saya sedang HOLD (Punya barang)")
    print("2. Saya mau ENTRY (Mau beli)")
    posisi_choice = input("Pilih (1/2): ")
    is_holding = True if posisi_choice == "1" else False

    avg_buy_price = 0.0
    total_investment = 0.0
    
    if is_holding:
        print(f"{Fore.YELLOW}--- INFO PORTOFOLIO ---{Style.RESET_ALL}")
        try:
            invest_input = input("Total Modal Awal ($)     : ")
            total_investment = float(invest_input) if invest_input else 1000.0
            price_input = input("Harga Beli Rata-Rata ($) : ")
            avg_buy_price = float(price_input) if price_input else 0.0
        except:
            print(f"{Fore.RED}Input error.{Style.RESET_ALL}")

    print("-" * 50)
    print(f"{Fore.CYAN}--- KONFIGURASI AKUN ---{Style.RESET_ALL}")
    try:
        equity = 1000.0 if is_holding else float(input("Total Modal Trading ($) [Default 1000]: ") or 1000.0)
        risk_per_trade = float(input("Risiko per Trade (%)    [Default 2%]: ") or 2.0)
    except:
        equity, risk_per_trade = 1000.0, 2.0

    # PROSES
    cached = database.load_cache(symbol)
    if cached:
        tech, ai = cached['tech'], cached['ai']
        # Fetch market data kilat (Sync karena ringan)
        market = technical.get_market_overview() 
        from_cache = True
    else:
        start = time.time()
        tech, ai, market = await run_analysis(symbol)
        if tech:
            database.save_cache(symbol, tech, ai)
            from_cache = False
        else:
            # Error handling sudah dilakukan di technical.py dengan print error
            print(f"{Fore.RED}Gagal ambil data. Cek pesan debug diatas.{Style.RESET_ALL}")
            return

    # =========================================================================
    # DISPLAY OUTPUT
    # =========================================================================
    
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════╗")
    print(f"║   ANALISA HYBRID: {symbol.ljust(10)}                        ║")
    print(f"╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}")
    
    # 1. MARKET WEATHER
    if market:
        m_color = Fore.GREEN if market['score'] > 0 else (Fore.RED if market['score'] < 0 else Fore.YELLOW)
        print(f"\n{Fore.WHITE}[ CUACA PASAR / MARKET WEATHER ]{Style.RESET_ALL}")
        print_kv("Kondisi Pasar", market['mood'], m_color)
        
        ndx_col = Fore.GREEN if market['nasdaq_change'] > 0 else Fore.RED
        spx_col = Fore.GREEN if market['sp500_change'] > 0 else Fore.RED
        print_kv("NASDAQ (Tech)", f"{market['nasdaq_change']:.2f}%", ndx_col)
        print_kv("S&P 500", f"{market['sp500_change']:.2f}%", spx_col)
        print("─" * 58)
    
    if from_cache: 
        print(f"{Fore.MAGENTA}[⚡ CACHED] Valid {config.CACHE_EXPIRY//60} menit.{Style.RESET_ALL}")
    
    current_price = tech['price']
    print(f"\n{Style.BRIGHT}HARGA SEKARANG     : ${current_price:,.2f}{Style.RESET_ALL}")
    
    # 2. MARKET STRUCTURE
    print(f"{Fore.YELLOW}[ STRUKTUR HARGA {symbol} ]{Style.RESET_ALL}")
    
    w_col = Fore.GREEN if "BULLISH" in tech['weekly_trend'] else Fore.RED
    print_kv("Weekly Trend", tech['weekly_trend'], w_col)
    
    d_col = Fore.GREEN if "UPTREND" in tech['daily_trend'] else (Fore.YELLOW if "CORRECTION" in tech['daily_trend'] else Fore.RED)
    print_kv("Daily Trend", tech['daily_trend'], d_col)
    
    print_kv("EMA 20 (Fast)", f"${tech['ema_20']:,.2f}", Fore.CYAN)
    
    r_col = Fore.RED if "MAHAL" in tech['rsi_desc'] else (Fore.GREEN if "DISKON" in tech['rsi_desc'] else Fore.WHITE)
    print_kv("RSI (14)", f"{tech['rsi']:.1f} ({tech['rsi_desc']})", r_col)

    m_col = Fore.GREEN if "POSITIF" in tech['macd_desc'] or "GOLDEN" in tech['macd_desc'] else Fore.RED
    print_kv("MACD Momentum", tech['macd_desc'], m_col)
    
    print("─" * 58)
    
    # 3. SENTIMEN AI
    score = ai.get('score', 0)
    ai_col = Fore.GREEN if score > 2 else (Fore.RED if score < -2 else Fore.WHITE)
    print_kv("AI News Score", f"{score}/10", ai_col)
    
    reason = ai.get('reason', 'N/A')
    formatted_reason = textwrap.fill(reason, width=55).replace("\n", "\n" + " " * 21)
    print(f"{'Alasan AI':<18} : {formatted_reason}")
    
    if ai.get('headlines'):
        print(f"\n{Fore.YELLOW}[SUMBER BERITA UTAMA]:{Style.RESET_ALL}")
        for i, h in enumerate(ai['headlines'][:3]):
            clean_h = h[:60] + "..." if len(h) > 60 else h
            print(f"  {i+1}. {clean_h}")

    print("─" * 58)

    # 4. STATISTIK PORTOFOLIO
    if is_holding and avg_buy_price > 0:
        shares_owned = total_investment / avg_buy_price
        current_value = shares_owned * current_price
        pl_dollar = current_value - total_investment
        pl_percent = ((current_price - avg_buy_price) / avg_buy_price) * 100
        pl_col = Fore.GREEN if pl_dollar >= 0 else Fore.RED
        pl_sign = "+" if pl_dollar >= 0 else ""

        print(f"{Fore.WHITE}┌────────────────────────────────────────────────────────┐")
        print(f"│                 STATISTIK PORTOFOLIO                   │")
        print(f"├────────────────────────────────────────────────────────┤{Style.RESET_ALL}")
        print(f"│ Harga Beli Avg   : ${avg_buy_price:,.2f}".ljust(57) + "│")
        print(f"│ Harga Sekarang   : ${current_price:,.2f}".ljust(57) + "│")
        print(f"│{Fore.WHITE}────────────────────────────────────────────────────────{Style.RESET_ALL}│")
        print(f"│ Total P/L ($)    : {pl_col}{pl_sign}${pl_dollar:,.2f}{Style.RESET_ALL}".ljust(66) + "│")
        print(f"│ Total P/L (%)    : {pl_col}{pl_sign}{pl_percent:.2f}%{Style.RESET_ALL}".ljust(66) + "│")
        print(f"{Fore.WHITE}└────────────────────────────────────────────────────────┘{Style.RESET_ALL}")

    # 5. STRATEGI FINAL
    print(f"\n{Fore.CYAN}=== KEPUTUSAN FINAL (DENGAN MARKET FILTER) ==={Style.RESET_ALL}")
    
    atr = tech['atr']
    support = tech['support']
    atr_sl_price = current_price - (2 * atr)
    
    market_is_bad = market and market['score'] < 0
    market_is_crash = market and market['score'] <= -2
    
    if is_holding:
        trailing_stop = max(support, atr_sl_price)
        if trailing_stop >= current_price: trailing_stop = current_price - atr
        
        print(f"{'[ POSISI ]':<18} : {Fore.YELLOW}HOLDING{Style.RESET_ALL}")
        
        if market_is_crash:
             print_kv("[ WARNING ]", "PASAR SEDANG CRASH!", Fore.RED)
             print_kv("[ SARAN ]", "PERTIMBANGKAN CASH OUT SEKARANG", Fore.RED)
        elif "BEARISH" in tech['weekly_trend']:
             print_kv("[ WARNING ]", "MAJOR TREND BEARISH", Fore.RED)
             print_kv("[ SARAN ]", "JUAL SAAT PANTULAN (Sell Strength)", Fore.YELLOW)
        elif "UPTREND" in tech['daily_trend'] and score > -2:
            print_kv("[ SARAN ]", "TAHAN (RIDE THE TREND)", Fore.GREEN)
            print_kv("[ TRAILING STOP ]", f"${trailing_stop:,.2f}", Fore.RED)
        else:
            print_kv("[ SARAN ]", "PERKETAT STOP LOSS", Fore.YELLOW)
            print_kv("[ STOP LOSS ]", f"${trailing_stop:,.2f}", Fore.RED)

    else:
        print(f"{'[ POSISI ]':<18} : {Fore.YELLOW}MENCARI ENTRY{Style.RESET_ALL}")
        
        entry_sl = min(support, atr_sl_price)
        risk_dist = current_price - entry_sl
        if risk_dist <= 0: risk_dist = atr
        
        max_loss = equity * (risk_per_trade / 100)
        shares = max_loss / risk_dist
        
        print_kv("[ STOP LOSS ]", f"${entry_sl:,.2f}", Fore.RED)
        
        if market_is_crash:
             print("─" * 58)
             print_kv("REKOMENDASI", "NO ENTRY (MARKET CRASH)", Fore.RED)
        elif "BEARISH" in tech['weekly_trend']:
             print("─" * 58)
             print_kv("REKOMENDASI", "NO ENTRY (WEEKLY BEARISH)", Fore.RED)
        elif "CORRECTION" in tech['daily_trend'] and score > 0 and not market_is_bad:
             print("─" * 58)
             print_kv("REKOMENDASI", "WAIT FOR BREAKOUT", Fore.YELLOW)
        elif "UPTREND" in tech['daily_trend'] and score > 2 and not market_is_bad:
            print("─" * 58)
            print_kv("REKOMENDASI", "BUY (BELI)", Fore.GREEN)
            print_kv("Max Lot", f"{int(shares)} Lembar", Fore.CYAN)
        else:
            print("─" * 58)
            print_kv("REKOMENDASI", "WAIT", Fore.WHITE)

    print("─" * 58)

if __name__ == "__main__":
    asyncio.run(main())