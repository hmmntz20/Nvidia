import os
from dotenv import load_dotenv
import google.generativeai as genai
from colorama import Fore, Style

# Load file .env
load_dotenv()

# --- KONFIGURASI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
JINA_API_KEY = os.getenv("JINA_API_KEY")

# Parameter Teknikal
SMA_PERIOD = int(os.getenv("SMA_PERIOD", 50))
RSI_PERIOD = int(os.getenv("RSI_PERIOD", 14))
RSI_OVERBOUGHT = int(os.getenv("RSI_OVERBOUGHT", 70))
RSI_OVERSOLD = int(os.getenv("RSI_OVERSOLD", 30))

# Cache
CACHE_EXPIRY = int(os.getenv("CACHE_EXPIRY", 300))
DB_FILE = "market_data.db"

# --- AUTO DETECT MODEL GEMINI ---
def setup_gemini_model():
    """Mencari model terbaik yang tersedia di akun Google AI kamu."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 1. Ambil daftar model yang tersedia
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except: pass

        # 2. Logika Prioritas
        target = os.getenv("GEMINI_MODEL", "")
        final_model = None

        # Cek apakah target di .env valid
        for m in available_models:
            if target in m and target != "":
                final_model = m; break
        
        # Jika tidak, cari Flash (Cepat & Murah)
        if not final_model:
            for m in available_models:
                if 'flash' in m: final_model = m; break
        
        # Jika tidak, cari Pro
        if not final_model:
            for m in available_models:
                if 'pro' in m: final_model = m; break

        # Fallback terakhir
        if not final_model: final_model = "gemini-1.5-flash"
        
        clean_name = final_model.replace("models/", "")
        return genai.GenerativeModel(clean_name)
        
    except Exception as e:
        print(f"{Fore.RED}Error Setup Gemini: {e}{Style.RESET_ALL}")
        return None

# Inisialisasi model di sini agar bisa diimport file lain
model = setup_gemini_model()