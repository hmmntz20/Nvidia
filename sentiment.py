import requests
import re
import json
import google.generativeai as genai
from datetime import datetime
from config import JINA_API_KEY, model
from colorama import Fore, Style # Biar error kelihatan merah

def get_jina_news(symbol):
    VIP_SOURCES = [
        "Reuters", "Bloomberg", "CNBC", "Financial Times", "Wall Street Journal", 
        "MarketWatch", "Barron's", "Forbes", "Business Insider", 
        "Tom's Hardware", "AnandTech", "Wccftech", "TechCrunch", "The Verge", "Yahoo Finance"
    ]
    
    vip_news = []
    regular_news = []
    
    # Teknik Dynamic Time Injection (Agar berita fresh)
    current_period = datetime.now().strftime("%B %Y")
    
    queries = [
        f"{symbol} supply chain news {current_period}", 
        f"latest {symbol} chip demand analysis {current_period}",
        f"{symbol} stock production update {current_period}"
    ]
    
    # Cek apakah API Key ada
    if not JINA_API_KEY:
        print(f"{Fore.RED}[ERROR] JINA_API_KEY Kosong di .env!{Style.RESET_ALL}")
        return []
    
    headers = {'Authorization': f'Bearer {JINA_API_KEY}', 'Accept': 'application/json'}
    
    print(f"{Fore.YELLOW}[DEBUG] Mencari berita via Jina...{Style.RESET_ALL}", end="\r")
    
    found_any = False
    
    for q in queries:
        try:
            url = f"https://s.jina.ai/{q}"
            response = requests.get(url, headers=headers, timeout=10)
            
            # --- DEBUGGING BLOCK ---
            if response.status_code != 200:
                print(f"{Fore.RED}[DEBUG] Jina Error {response.status_code}: {response.text[:50]}...{Style.RESET_ALL}")
                continue
            # -----------------------

            if response.status_code == 200:
                data = response.json().get('data', [])
                if data: found_any = True
                
                for item in data:
                    title = item.get('title', 'No Title')
                    content = item.get('content', '')[:500].replace("\n", " ")
                    source = item.get('url', '')
                    
                    formatted = f"Title: {title}\nSummary: {content}...\nSource: {source}\n"
                    
                    is_vip = any(vip.lower() in source.lower() for vip in VIP_SOURCES)
                    if is_vip: vip_news.append(formatted)
                    else: regular_news.append(formatted)
        except Exception as e:
            print(f"{Fore.RED}[DEBUG] Connection Error: {e}{Style.RESET_ALL}")
            continue

    if not found_any:
        print(f"{Fore.RED}[DEBUG] Jina return 200 OK tapi tidak ada artikel.{Style.RESET_ALL}")

    # Anti-Shuffle Logic
    final_news = list(dict.fromkeys(vip_news))
    
    if len(final_news) < 6:
        needed = 6 - len(final_news)
        final_news.extend(list(dict.fromkeys(regular_news))[:needed])
        
    return final_news[:6]

async def analyze_sentiment(news_list, symbol):
    if not news_list:
        return {'score': 0, 'reason': 'Tidak ada berita (Cek API Key / Koneksi)', 'headlines': []}
    
    headlines_debug = [n.split('\n')[0].replace("Title: ", "") for n in news_list]
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Role: Senior Financial Analyst. 
    Current Date: {today_date}.
    Task: Analyze news for {symbol}.
    
    DATA: 
    {chr(10).join(news_list)}
    
    INSTRUCTIONS:
    1. IGNORE news older than 30 days.
    2. Analyze Sentiment (-10 to +10).
    3. Summarize reason in 1 sentence.
    
    RETURN JSON ONLY: {{"score": 0, "reason": "Summary"}}
    """
    
    try:
        config = genai.types.GenerationConfig(temperature=0.0)
        response = await model.generate_content_async(prompt, generation_config=config)
        
        text = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(re.search(r'\{.*\}', text, re.DOTALL).group(0))
        result['headlines'] = headlines_debug
        return result
    except Exception as e:
        return {'score': 0, 'reason': f"AI Error: {str(e)}", 'headlines': []}