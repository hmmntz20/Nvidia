import asyncio
import os
import contextlib
import sys
import json
import time
import sqlite3
import requests 
from dotenv import load_dotenv
import warnings

# BUNGKAM WARNING
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings("ignore")

try:
    import yfinance as yf
    import google.generativeai as genai
    import pandas as pd
    import re 
    from colorama import Fore, Style, init
except ImportError as e:
    print(f"Error Library: {e}")
    print("Pastikan install: pip install yfinance google-generativeai pandas colorama python-dotenv requests")
    exit()

# --- LOAD KONFIGURASI ---
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
JINA_API_KEY = os.getenv("JINA_API_KEY") 
SMA_PERIOD = int(os.getenv("SMA_PERIOD", 50))
RSI_PERIOD = int(os.getenv("RSI_PERIOD", 14))
CACHE_EXPIRY = int(os.getenv("CACHE_EXPIRY", 300)) 

DB_FILE = "market_data.db"

init(autoreset=True)

# --- SETUP GEMINI (DENGAN AUTO-DETECT YANG HILANG KEMARIN) ---
# Fitur ini memastikan kita tidak kena Error 404 kalau nama model ganti
try:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # 1. Cek Model yang Tersedia di Akun ini
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except: pass

    # 2. Prioritas Pemilihan (Config -> Flash -> Pro -> Apa aja)
    target_model_name = os.getenv("GEMINI_MODEL", "")
    final_model = None
    
    # Cek apakah model di .env valid
    for m in available_models:
        if target_model_name in m and target_model_name != "":
            final_model = m
            break
            
    # Jika tidak valid, cari Flash (Cepat & Murah)
    if not final_model:
        for m in available_models:
            if 'flash' in m: final_model = m; break
            
    # Jika tidak ada Flash, cari Pro
    if not final_model:
        for m in available_models:
            if 'pro' in m: final_model = m; break
            
    # Fallback terakhir
    if not final_model and available_models: final_model = available_models[0]
    if not final_model: final_model = "gemini-1.5-flash" # Harapan terakhir
    
    # Bersihkan nama (kadang ada prefix 'models/')
    clean_model_name = final_model.replace("models/", "")
    model = genai.GenerativeModel(clean_model_name)
    
except Exception as e:
    print(f"{Fore.RED}Gagal Setup Gemini: {e}{Style.RESET_ALL}")
    exit()

# --- SISTEM DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stock_cache
                 (symbol TEXT PRIMARY KEY, data TEXT, timestamp REAL)''')
    conn.commit()
    conn.close()

def load_cache_db(symbol):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT data, timestamp FROM stock_cache WHERE symbol = ?", (symbol,))
    result = c.fetchone()
    conn.close()
    
    if result:
        data_json, timestamp = result
        if time.time() - timestamp < CACHE_EXPIRY:
            return json.loads(data_json)
    return None

def save_cache_db(symbol, tech_data, ai_data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    full_data = {'tech': tech_data, 'ai': ai_data}
    json_str = json.dumps(full_data)
    c.execute("INSERT OR REPLACE INTO stock_cache (symbol, data, timestamp) VALUES (?, ?, ?)",
              (symbol, json_str, time.time()))
    conn.commit()
    conn.close()

init_db()

# --- FUNGSI TEKNIKAL ---
def sync_get_technical(symbol):
    try:
        # Silencer tetap dipakai disini karena yfinance kadang berisik
        with open(os.devnull, 'w') as fnull:
            with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                df = yf.download(tickers=symbol, period="6mo", interval="1d", progress=False)
        
        if df.empty or len(df) < 50: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.rename(columns={'Close': 'close', 'Volume': 'volume'}, inplace=True)

        df['SMA'] = df['close'].rolling(SMA_PERIOD).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        rs = gain.rolling(RSI_PERIOD).mean() / loss.rolling(RSI_PERIOD).mean()
        df['RSI'] = 100 - (100 / (1 + rs))

        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist'] = df['MACD'] - df['Signal']

        df['Vol_Avg'] = df['volume'].rolling(20).mean()

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        trend = "UPTREND" if curr['close'] > curr['SMA'] else "DOWNTREND"
        
        rsi_desc = "NETRAL"
        if curr['RSI'] > 70: rsi_desc = "MAHAL (Overbought)"
        if curr['RSI'] < 30: rsi_desc = "DISKON (Oversold)"
        
        macd_desc = "NETRAL"
        if curr['Hist'] > 0 and prev['Hist'] < 0: macd_desc = "GOLDEN CROSS"
        elif curr['Hist'] < 0 and prev['Hist'] > 0: macd_desc = "DEATH CROSS"
        elif curr['Hist'] > 0: macd_desc = "POSITIF"
        else: macd_desc = "NEGATIF"

        vol_desc = "RENDAH"
        if curr['volume'] > curr['Vol_Avg']: vol_desc = "TINGGI (Valid)"

        return {
            'price': float(curr['close']),
            'trend': trend,
            'rsi': float(curr['RSI']),
            'rsi_desc': rsi_desc,
            'macd_desc': macd_desc,
            'vol_desc': vol_desc
        }
    except Exception: return None

# --- FUNGSI SEARCH JINA (ANTI-SHUFFLE + VIP) ---
def sync_get_news_jina(symbol):
    VIP_SOURCES = [
        "Reuters", "Bloomberg", "CNBC", "Financial Times", "Wall Street Journal", 
        "MarketWatch", "Barron's", "Forbes", "Business Insider", 
        "Tom's Hardware", "AnandTech", "Wccftech", "TechCrunch", "The Verge", "Yahoo Finance"
    ]
    
    vip_news = []
    regular_news = []
    
    queries = [
        f"{symbol} supply chain shortage production",
        f"{symbol} chip demand orders analysis"
    ]
    
    headers = {
        'Authorization': f'Bearer {JINA_API_KEY}', 
        'Accept': 'application/json' 
    }
    
    for q in queries:
        try:
            url = f"https://s.jina.ai/{q}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                json_data = response.json()
                if 'data' in json_data:
                    for item in json_data['data']:
                        title = item.get('title', 'No Title')
                        content = item.get('content', '') 
                        url_source = item.get('url', '')
                        
                        snippet = content[:500].replace("\n", " ")
                        formatted = f"Title: {title}\nSummary: {snippet}...\nSource: {url_source}\n"
                        
                        is_vip = False
                        for vip in VIP_SOURCES:
                            if vip.lower() in url_source.lower() or vip.lower() in title.lower():
                                is_vip = True
                                break
                        
                        if is_vip:
                            vip_news.append(formatted)
                        else:
                            regular_news.append(formatted)
        except Exception: continue

    # FIX SHUFFLE: Gunakan dict.fromkeys agar urutan tidak acak
    final_news = list(dict.fromkeys(vip_news))
    
    if len(final_news) < 5:
        needed = 5 - len(final_news)
        regular_unique = list(dict.fromkeys(regular_news))
        final_news.extend(regular_unique[:needed])
        
    return final_news[:6]

async def get_analysis_parallel(symbol):
    loop = asyncio.get_running_loop()
    
    print(f"{Fore.YELLOW}>> Memulai Analisa Jina AI & Teknikal...{Style.RESET_ALL}", end="\r")
    
    task_tech = loop.run_in_executor(None, sync_get_technical, symbol)
    task_search = loop.run_in_executor(None, sync_get_news_jina, symbol)
    
    tech_result, news_result = await asyncio.gather(task_tech, task_search)
    
    ai_result = {'score': 0, 'reason': 'Data tidak cukup/Error', 'headlines': []}
    
    if news_result:
        print(f"{Fore.YELLOW}>> Mengirim Data Jina ke Gemini AI...            {Style.RESET_ALL}", end="\r")
        
        headlines_debug = [n.split('\n')[0].replace("Title: ", "") for n in news_result]
        
        # PROMPT BARU: CHAIN OF THOUGHT (CoT)
        prompt = f"""
        Role: Senior Financial Analyst. 
        Task: Analyze the provided news snippets for {symbol} specifically regarding Supply Chain & Demand.
        
        DATA:
        {chr(10).join(news_result)}
        
        INSTRUCTIONS:
        1. Identify KEY POSITIVE factors (e.g., high demand, solved issues).
        2. Identify KEY NEGATIVE factors (e.g., shortages, delays, bans).
        3. WEIGH the evidence. Do the negatives outweigh the positives significantly?
        4. Assign a Sentiment Score from -10 (Catastrophic) to +10 (Phenomenal). 0 is Neutral/Mixed.
        5. Write a 1-sentence analytical summary.
        
        RETURN JSON ONLY:
        {{"score": 0, "reason": "Your analytical summary here"}}
        """
        try:
            config = genai.types.GenerationConfig(temperature=0.0)
            response = await model.generate_content_async(prompt, generation_config=config)
            
            raw_text = response.text
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                ai_result = json.loads(match.group(0))
            else:
                ai_result = json.loads(raw_text.replace("```json", "").replace("```", "").strip())
            
            ai_result['headlines'] = headlines_debug
            
        except Exception as e:
            ai_result['reason'] = f"AI Error: {str(e)}"
            
    return tech_result, ai_result

# --- MAIN PROGRAM ---
async def main():
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{Fore.GREEN}=== AI TRADER PRO (V12: ULTIMATE EDITION) ==={Style.RESET_ALL}")
    
    symbol_input = input("Masukkan Kode Saham: ").upper()
    if not symbol_input: symbol_input = "NVDA"
    print("-" * 50)
    
    cached_full = load_cache_db(symbol_input)
    
    if cached_full:
        print(f"{Fore.MAGENTA}>> Data ditemukan di Database (Hemat API & Waktu!){Style.RESET_ALL}")
        tech_data = cached_full['tech']
        ai_result = cached_full['ai']
        from_cache = True
    else:
        start_time = time.time()
        tech_data, ai_result = await get_analysis_parallel(symbol_input)
        end_time = time.time()
        
        if tech_data:
            save_cache_db(symbol_input, tech_data, ai_result)
            print(f"{Fore.BLUE}>> Analisa Selesai dalam {end_time - start_time:.2f} detik.{Style.RESET_ALL}")
            from_cache = False
        else:
            print(f"{Fore.RED}Gagal mengambil data pasar.{Style.RESET_ALL}")
            return

    if tech_data:
        os.system('clear' if os.name == 'posix' else 'cls')
        print(f"{Fore.CYAN}╔════════════════════════════════════════════╗")
        title_text = f"ANALISA HYBRID: {symbol_input}"
        print(f"║   {title_text.ljust(40)} ║")
        print(f"╚════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        if from_cache:
            menit = CACHE_EXPIRY // 60
            print(f"{Fore.MAGENTA}[⚡ DATABASE CACHE] - Data valid selama {menit} menit.{Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}HARGA : ${tech_data['price']:,.2f}{Style.RESET_ALL}")
        print("-" * 46)
        
        t_col = Fore.GREEN if tech_data['trend'] == "UPTREND" else Fore.RED
        print(f"[TREND]     : {t_col}{tech_data['trend']} (SMA {SMA_PERIOD}){Style.RESET_ALL}")
        
        r_col = Fore.RED if "MAHAL" in tech_data['rsi_desc'] else (Fore.GREEN if "DISKON" in tech_data['rsi_desc'] else Fore.WHITE)
        print(f"[RSI]       : {r_col}{tech_data['rsi']:.2f} -> {tech_data['rsi_desc']}{Style.RESET_ALL}")
        
        m_col = Fore.GREEN if "POSITIF" in tech_data['macd_desc'] or "GOLDEN" in tech_data['macd_desc'] else Fore.RED
        print(f"[MACD]      : {m_col}{tech_data['macd_desc']}{Style.RESET_ALL}")
        
        v_col = Fore.GREEN if "TINGGI" in tech_data['vol_desc'] else Fore.YELLOW
        print(f"[VOLUME]    : {v_col}{tech_data['vol_desc']}{Style.RESET_ALL}")
        
        print("-" * 46)
        
        score = ai_result.get('score', 0)
        reason = ai_result.get('reason', 'N/A')
        headlines = ai_result.get('headlines', [])

        ai_col = Fore.GREEN if score > 2 else (Fore.RED if score < -2 else Fore.WHITE)
        if score == 0 and not headlines:
            print(f"{Fore.YELLOW}[DEBUG] Skor 0. Jina tidak menemukan berita atau API Key salah.{Style.RESET_ALL}")
        
        print(f"[AI NEWS]   : {ai_col}Score {score}/10{Style.RESET_ALL}")
        print(f"[AI REASON] : \"{reason}\"")
        
        if headlines:
            print(f"{Fore.YELLOW}[SUMBER BERITA JINA]:{Style.RESET_ALL}")
            for i, h in enumerate(headlines):
                print(f"  {i+1}. {h[:80]}...") 
        
        print("-" * 46)
        
        final_verdict = "WAIT"
        final_col = Fore.WHITE
        
        if tech_data['trend'] == "UPTREND" and score >= 4 and "POSITIF" in tech_data['macd_desc']:
            final_verdict = "STRONG BUY (All Green)"
            final_col = Fore.GREEN
        elif tech_data['trend'] == "UPTREND" and score >= 4 and tech_data['rsi'] < 40:
             final_verdict = "BUY ON DIP"
             final_col = Fore.CYAN
        elif tech_data['trend'] == "DOWNTREND" and score > 6 and tech_data['rsi'] < 30:
            final_verdict = "RISKY BUY (Speculative)"
            final_col = Fore.YELLOW
        elif tech_data['trend'] == "UPTREND" and score < -2:
            final_verdict = "WASPADA (Bull Trap)"
            final_col = Fore.MAGENTA
        elif tech_data['trend'] == "DOWNTREND":
            final_verdict = "JANGAN SENTUH"
            final_col = Fore.RED
            
        print(f"KEPUTUSAN : {final_col}{Style.BRIGHT}{final_verdict}{Style.RESET_ALL}")
        print("-" * 46)

if __name__ == "__main__":
    asyncio.run(main())