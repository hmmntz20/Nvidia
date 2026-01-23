import requests
import os
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

JINA_KEY = os.getenv("JINA_API_KEY")

print(f"{Fore.CYAN}--- DIAGNOSA JINA AI ---{Style.RESET_ALL}")

if not JINA_KEY:
    print(f"{Fore.RED}[FATAL] Kunci JINA_API_KEY tidak terbaca oleh Python!{Style.RESET_ALL}")
    print("Pastikan file .env ada di folder yang sama dengan script ini.")
    exit()

print(f"Kunci Terdeteksi: {JINA_KEY[:5]}********")

# Test Query Sederhana
url = "https://s.jina.ai/Nvidia stock news"
headers = {
    'Authorization': f'Bearer {JINA_KEY}',
    'Accept': 'application/json'
}

print("Sedang menghubungi server Jina...")
try:
    response = requests.get(url, headers=headers, timeout=15)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        items = data.get('data', [])
        print(f"{Fore.GREEN}Sukses! Ditemukan {len(items)} artikel.{Style.RESET_ALL}")
        if items:
            print(f"Contoh Judul: {items[0].get('title')}")
        else:
            print(f"{Fore.YELLOW}Tapi datanya kosong (List []).{Style.RESET_ALL}")
            print("Response Mentah:", response.text[:500])
    elif response.status_code == 401:
        print(f"{Fore.RED}Error 401: Unauthorized. Kunci salah atau format salah.{Style.RESET_ALL}")
    elif response.status_code == 402:
        print(f"{Fore.RED}Error 402: Payment Required. Kuota gratis habis.{Style.RESET_ALL}")
    elif response.status_code == 429:
        print(f"{Fore.RED}Error 429: Rate Limit. Terlalu banyak request.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}Error Lain: {response.text}{Style.RESET_ALL}")

except Exception as e:
    print(f"{Fore.RED}Koneksi Gagal: {e}{Style.RESET_ALL}")