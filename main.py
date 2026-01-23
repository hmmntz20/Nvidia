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
    task_tech = loop.run_in_executor(None, technical.get_technical_analysis, symbol)
    task_news = loop.run_in_executor(None, sentiment.get_jina_news, symbol)
    
    tech_data, news_list = await asyncio.gather(task_tech, task_news)
    
    print(f"{Fore.YELLOW}>> Mengirim ke Gemini AI...      {Style.RESET_ALL}", end="\r")
    ai_result = await sentiment.analyze_sentiment(news_list, symbol)
    
    return tech_data, ai_result

# Fungsi Helper untuk print rapi
def print_kv(key, value, color=Fore.WHITE):
    print(f"{key:<18} : {color}{value}{Style.RESET_ALL}")

async def main():
    database.init_db()
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Fore.GREEN}=== AI TRADER PRO (CLEAN UI V16) ==={Style.RESET_ALL}")
    
    symbol = input("Masukkan Kode Saham: ").upper() or "NVDA"
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
        if not is_holding:
            equity_input = input("Total Modal Trading ($) [Default 1000]: ")
            equity = float(equity_input) if equity_input else 1000.0
        else:
            equity = 1000.0
        
        risk_input = input("Risiko per Trade (%)    [Default 2%]: ")
        risk_per_trade = float(risk_input) if risk_input else 2.0
    except:
        equity = 1000.0
        risk_per_trade = 2.0

    # PROSES
    cached = database.load_cache(symbol)
    if cached:
        tech, ai = cached['tech'], cached['ai']
        from_cache = True
    else:
        start = time.time()
        tech, ai = await run_analysis(symbol)
        if tech:
            database.save_cache(symbol, tech, ai)
            from_cache = False
        else:
            print(f"{Fore.RED}Gagal ambil data.{Style.RESET_ALL}"); return

    # =========================================================================
    # DISPLAY OUTPUT (YANG DIPERBAIKI)
    # =========================================================================
    
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # 1. HEADER
    print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════╗")
    print(f"║   ANALISA HYBRID: {symbol.ljust(10)}                             ║")
    print(f"╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}")
    
    if from_cache: 
        print(f"{Fore.MAGENTA}[⚡ CACHED] Valid {config.CACHE_EXPIRY//60} menit.{Style.RESET_ALL}")
    
    current_price = tech['price']
    print(f"\n{Style.BRIGHT}HARGA SEKARANG     : ${current_price:,.2f}{Style.RESET_ALL}")
    print("─" * 58)
    
    # 2. DATA PASAR (Rata Kiri Rapi)
    t_col = Fore.GREEN if tech['trend'] == "UPTREND" else Fore.RED
    print_kv("Trend Utama", tech['trend'], t_col)
    
    r_col = Fore.RED if "MAHAL" in tech['rsi_desc'] else (Fore.GREEN if "DISKON" in tech['rsi_desc'] else Fore.WHITE)
    print_kv("RSI (14)", f"{tech['rsi']:.1f} ({tech['rsi_desc']})", r_col)

    m_col = Fore.GREEN if "POSITIF" in tech['macd_desc'] or "GOLDEN" in tech['macd_desc'] else Fore.RED
    print_kv("MACD Momentum", tech['macd_desc'], m_col)
    
    v_col = Fore.GREEN if "TINGGI" in tech['vol_desc'] else Fore.YELLOW
    print_kv("Volume Activity", tech['vol_desc'], v_col)
    
    print("─" * 58)
    
    # 3. SENTIMEN AI (Rata Kiri + Text Wrap)
    score = ai.get('score', 0)
    ai_col = Fore.GREEN if score > 2 else (Fore.RED if score < -2 else Fore.WHITE)
    print_kv("AI News Score", f"{score}/10", ai_col)
    
    reason = ai.get('reason', 'N/A')
    # Wrap text agar tidak melebar
    wrapped_reason = textwrap.fill(reason, width=55)
    # Indentasi baris kedua dst
    formatted_reason = wrapped_reason.replace("\n", "\n" + " " * 21)
    
    print(f"{'Alasan AI':<18} : {formatted_reason}")
    
    if ai.get('headlines'):
        print(f"\n{Fore.YELLOW}[SUMBER BERITA UTAMA]:{Style.RESET_ALL}")
        for i, h in enumerate(ai['headlines'][:3]):
            clean_h = h[:60] + "..." if len(h) > 60 else h
            print(f"  {i+1}. {clean_h}")

    print("─" * 58)

    # 4. STATISTIK PORTOFOLIO (Kotak Rapi)
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
        print(f"│ Jumlah Lembar    : {shares_owned:.2f} lembar".ljust(57) + "│")
        print(f"│{Fore.WHITE}────────────────────────────────────────────────────────{Style.RESET_ALL}│")
        print(f"│ Modal Awal       : ${total_investment:,.2f}".ljust(57) + "│")
        print(f"│ Nilai Sekarang   : {pl_col}${current_value:,.2f}{Style.RESET_ALL}".ljust(66) + "│")
        
        pld_str = f"{pl_sign}${pl_dollar:,.2f}"
        plp_str = f"{pl_sign}{pl_percent:.2f}%"
        print(f"│ Total P/L ($)    : {pl_col}{pld_str:<15}{Style.RESET_ALL}".ljust(66) + "│")
        print(f"│ Total P/L (%)    : {pl_col}{plp_str:<15}{Style.RESET_ALL}".ljust(66) + "│")
        print(f"{Fore.WHITE}└────────────────────────────────────────────────────────┘{Style.RESET_ALL}")

    # 5. RISK MANAGEMENT PLAN (Lebih Terstruktur)
    print(f"\n{Fore.CYAN}=== RISK MANAGEMENT PLAN ==={Style.RESET_ALL}")
    
    atr = tech['atr']
    support = tech['support']
    atr_sl_price = current_price - (2 * atr)
    
    if is_holding:
        trailing_stop = max(support, atr_sl_price)
        if trailing_stop >= current_price: trailing_stop = current_price - atr
        
        print(f"{'[ POSISI ]':<18} : {Fore.YELLOW}HOLDING{Style.RESET_ALL}")
        
        is_uptrend = tech['trend'] == "UPTREND"
        is_bad_news = score < -3
        
        if is_uptrend and not is_bad_news:
            print_kv("[ SARAN ]", "TAHAN (HOLD)", Fore.GREEN)
            print_kv("[ STRATEGI ]", "Pasang Trailing Stop untuk kunci profit")
            print_kv("[ TRAILING STOP ]", f"${trailing_stop:,.2f}", Fore.RED)
        elif is_bad_news:
            print_kv("[ SARAN ]", "WASPADA / JUAL SEBAGIAN", Fore.RED)
            print_kv("[ ALASAN ]", f"Berita Buruk (Score {score}). Potensi Reversal.")
            print_kv("[ SUPPORT KRITIS ]", f"${support:,.2f} (Jika jebol, EXIT)", Fore.YELLOW)
        else:
            print_kv("[ SARAN ]", "PERKETAT STOP LOSS", Fore.YELLOW)
            print_kv("[ STOP LOSS ]", f"${trailing_stop:,.2f}", Fore.RED)

    else:
        print(f"{'[ POSISI ]':<18} : {Fore.YELLOW}MENCARI ENTRY{Style.RESET_ALL}")
        
        entry_sl = min(support, atr_sl_price)
        risk_dist = current_price - entry_sl
        target_price = current_price + (2 * risk_dist)
        if risk_dist <= 0: risk_dist = atr
        
        max_loss = equity * (risk_per_trade / 100)
        shares = max_loss / risk_dist
        capital_needed = shares * current_price
        
        print_kv("[ STOP LOSS ]", f"${entry_sl:,.2f}", Fore.RED)
        print_kv("[ TARGET PROFIT ]", f"${target_price:,.2f}", Fore.GREEN)
        
        if tech['trend'] == "UPTREND" and score > 2:
            print("─" * 58)
            print_kv("REKOMENDASI", "BUY (BELI)", Fore.GREEN)
            print_kv("Max Lot", f"{int(shares)} Lembar", Fore.CYAN)
            print_kv("Modal Entry", f"${capital_needed:,.2f}")
            print_kv("Resiko Max", f"${max_loss:.2f} ({risk_per_trade}%)")
        else:
            print("─" * 58)
            print_kv("REKOMENDASI", "WAIT (JANGAN MASUK)", Fore.RED)
            print_kv("Alasan", "Tren belum Uptrend atau Berita Negatif")

    print("─" * 58)

if __name__ == "__main__":
    asyncio.run(main())