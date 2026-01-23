import asyncio
import os
import time
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

async def main():
    database.init_db()
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Fore.GREEN}=== AI TRADER PRO (RISK MANAGER V14) ==={Style.RESET_ALL}")
    
    symbol = input("Masukkan Kode Saham: ").upper() or "NVDA"
    
    # --- FITUR BARU: HOLD vs ENTRY ---
    print("\nApa status kamu saat ini?")
    print("1. Saya sedang PEGANG saham ini (Hold)")
    print("2. Saya mau BELI saham ini (Entry)")
    posisi_input = input("Pilih (1/2): ")
    is_holding = True if posisi_input == "1" else False
    
    print("-" * 50)
    
    # Cek Cache
    cached = database.load_cache(symbol)
    if cached:
        print(f"{Fore.MAGENTA}>> Data dari Database (Cache){Style.RESET_ALL}")
        tech, ai = cached['tech'], cached['ai']
        from_cache = True
    else:
        start = time.time()
        tech, ai = await run_analysis(symbol)
        if tech:
            database.save_cache(symbol, tech, ai)
            print(f"{Fore.BLUE}>> Selesai dalam {time.time()-start:.2f} detik.{Style.RESET_ALL}")
            from_cache = False
        else:
            print(f"{Fore.RED}Gagal ambil data.{Style.RESET_ALL}"); return

    # --- DISPLAY HASIL ---
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Fore.CYAN}╔════════════════════════════════════════════╗")
    print(f"║   ANALISA HYBRID: {symbol.ljust(10)}               ║")
    print(f"╚════════════════════════════════════════════╝{Style.RESET_ALL}")
    
    if from_cache:
        print(f"{Fore.MAGENTA}[⚡ CACHED] Valid {config.CACHE_EXPIRY//60} menit.{Style.RESET_ALL}")

    print(f"\nHARGA SAAT INI : ${tech['price']:,.2f}")
    print("-" * 46)
    
    # --- BAGIAN TEKNIKAL LENGKAP (SUDAH DIKEMBALIKAN) ---
    t_col = Fore.GREEN if tech['trend'] == "UPTREND" else Fore.RED
    print(f"[TREND]   : {t_col}{tech['trend']}{Style.RESET_ALL}")
    
    r_col = Fore.RED if "MAHAL" in tech['rsi_desc'] else (Fore.GREEN if "DISKON" in tech['rsi_desc'] else Fore.WHITE)
    print(f"[RSI]     : {r_col}{tech['rsi']:.2f} ({tech['rsi_desc']}){Style.RESET_ALL}")

    # INI YANG KEMARIN HILANG, SEKARANG ADA LAGI
    m_col = Fore.GREEN if "POSITIF" in tech['macd_desc'] or "GOLDEN" in tech['macd_desc'] else Fore.RED
    print(f"[MACD]    : {m_col}{tech['macd_desc']}{Style.RESET_ALL}")
    
    v_col = Fore.GREEN if "TINGGI" in tech['vol_desc'] else Fore.YELLOW
    print(f"[VOLUME]  : {v_col}{tech['vol_desc']}{Style.RESET_ALL}")
    
    print("-" * 46)
    
    # --- BAGIAN AI ---
    score = ai.get('score', 0)
    ai_col = Fore.GREEN if score > 2 else (Fore.RED if score < -2 else Fore.WHITE)
    print(f"[AI NEWS] : {ai_col}Score {score}/10{Style.RESET_ALL}")
    print(f"[REASON]  : {ai.get('reason')}")
    
    if ai.get('headlines'):
        print(f"{Fore.YELLOW}[SUMBER]:{Style.RESET_ALL}")
        # Tampilkan 3 berita saja biar rapi, tapi AI baca 6
        for i, h in enumerate(ai['headlines'][:3]):
            print(f"  {i+1}. {h[:60]}...")

    print("-" * 46)
    
    # --- LOGIKA KEPUTUSAN & RISK MANAGEMENT ---
    print(f"{Fore.CYAN}=== STRATEGI & RISK MANAGEMENT ==={Style.RESET_ALL}")
    
    # Hitung level penting
    support = tech['support']
    resistance = tech['resistance']
    stop_loss = support * 0.98 # Stop loss 2% dibawah support
    
    if is_holding:
        # STRATEGI KALAU LAGI HOLD
        print(f"Posisi: {Fore.YELLOW}HOLDING{Style.RESET_ALL}")
        
        if tech['trend'] == "UPTREND" and score > -2:
            print(f"Saran: {Fore.GREEN}TAHAN (LET PROFIT RUN){Style.RESET_ALL}")
            print(f"Pasang Trailing Stop di: ${support:.2f}")
        elif tech['trend'] == "DOWNTREND" or score < -4:
            print(f"Saran: {Fore.RED}PERTIMBANGKAN JUAL/CUT LOSS{Style.RESET_ALL}")
            print(f"Alasan: Tren turun atau Berita sangat buruk.")
            print(f"Support Terdekat (Lantai): ${support:.2f}")
        else:
            print(f"Saran: {Fore.WHITE}WAIT & SEE{Style.RESET_ALL}")
            print(f"Jaga Stop Loss Ketat di: ${stop_loss:.2f}")
            
    else:
        # STRATEGI KALAU MAU ENTRY (BELI)
        print(f"Posisi: {Fore.YELLOW}MENCARI ENTRY{Style.RESET_ALL}")
        
        if tech['trend'] == "UPTREND" and score >= 4:
            print(f"Saran: {Fore.GREEN}BOLEH BELI (STRONG BUY){Style.RESET_ALL}")
            print(f"Entry Ideal: Sekarang atau tunggu koreksi sedikit.")
            print(f"Target Profit: ${resistance:.2f}")
            print(f"Stop Loss Wajib: ${stop_loss:.2f}")
        elif tech['trend'] == "UPTREND" and score < -2:
            print(f"Saran: {Fore.MAGENTA}JANGAN MASUK (BULL TRAP){Style.RESET_ALL}")
            print("Harga naik tapi berita jelek. Berisiko tinggi.")
        elif tech['rsi'] < 30 and score > 0:
            print(f"Saran: {Fore.CYAN}SPECULATIVE BUY (PANTULAN){Style.RESET_ALL}")
            print("Ambil pantulan pendek (Scalping).")
        else:
            print(f"Saran: {Fore.RED}JANGAN MASUK (WAIT){Style.RESET_ALL}")
            print("Tren belum jelas atau berita buruk.")

    print("-" * 46)

if __name__ == "__main__":
    asyncio.run(main())