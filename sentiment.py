import requests
import re
import json
import google.generativeai as genai
from datetime import datetime # <--- PENTING BUAT CEK WAKTU
from config import JINA_API_KEY, model

def get_jina_news(symbol):
    VIP_SOURCES = [
        "Reuters", "Bloomberg", "CNBC", "Financial Times", "Wall Street Journal", 
        "MarketWatch", "Barron's", "Forbes", "Business Insider", 
        "Tom's Hardware", "AnandTech", "Wccftech", "TechCrunch", "The Verge", "Yahoo Finance"
    ]
    
    vip_news = []
    regular_news = []
    current_period = datetime.now().strftime("%B %Y")
    
    queries = [
        f"{symbol} supply chain news {current_period}", # e.g. "NVDA supply chain news January 2026"
        f"latest {symbol} chip demand analysis {current_period}",
        f"{symbol} stock production update {current_period}"
    ]
    
    headers = {'Authorization': f'Bearer {JINA_API_KEY}', 'Accept': 'application/json'}
    
    for q in queries:
        try:
            url = f"https://s.jina.ai/{q}"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json().get('data', [])
                for item in data:
                    title = item.get('title', 'No Title')
                    # Ambil 500 karakter konten
                    content = item.get('content', '')[:500].replace("\n", " ")
                    source = item.get('url', '')
                    
                    # Tambahkan Date Metadata jika ada (Jina kadang kasih, kadang nggak)
                    # Tapi dengan Query Injection di atas, kontennya harusnya relevan.
                    formatted = f"Title: {title}\nSummary: {content}...\nSource: {source}\n"
                    
                    is_vip = any(vip.lower() in source.lower() for vip in VIP_SOURCES)
                    if is_vip: vip_news.append(formatted)
                    else: regular_news.append(formatted)
        except: continue

    # Anti-Shuffle Logic
    final_news = list(dict.fromkeys(vip_news))
    
    if len(final_news) < 6:
        needed = 6 - len(final_news)
        final_news.extend(list(dict.fromkeys(regular_news))[:needed])
        
    return final_news[:6]

async def analyze_sentiment(news_list, symbol):
    if not news_list:
        return {'score': 0, 'reason': 'Tidak ada berita', 'headlines': []}
    
    headlines_debug = [n.split('\n')[0].replace("Title: ", "") for n in news_list]
    
    # --- TEKNIK 2: AI DATE VALIDATION ---
    # Kita beritahu AI tanggal hari ini, dan suruh dia jadi satpam.
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Role: Senior Financial Analyst. 
    Current Date: {today_date} (YYYY-MM-DD).
    
    Task: Analyze news for {symbol}.
    
    DATA: 
    {chr(10).join(news_list)}
    
    CRITICAL INSTRUCTION (RECENCY CHECK):
    1. Check for time markers in the text (e.g., "2 days ago", "last week", dates).
    2. IGNORE any news that is clearly older than 30 days from {today_date}.
    3. If a news item is old, do not include it in the Sentiment Score calculation.
    
    ANALYSIS STEPS:
    1. Identify KEY POSITIVE factors (Fresh news only).
    2. Identify KEY NEGATIVE factors (Fresh news only).
    3. Weigh the evidence (-10 to +10).
    4. Summarize the reason in 1 sentence.
    
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