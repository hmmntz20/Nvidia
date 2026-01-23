import requests
import re
import json
import google.generativeai as genai
from config import JINA_API_KEY, model

def get_jina_news(symbol):
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
    
    headers = {'Authorization': f'Bearer {JINA_API_KEY}', 'Accept': 'application/json'}
    
    for q in queries:
        try:
            url = f"https://s.jina.ai/{q}"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json().get('data', [])
                for item in data:
                    title = item.get('title', 'No Title')
                    # Ambil 500 karakter biar AI gak pusing
                    content = item.get('content', '')[:500].replace("\n", " ")
                    source = item.get('url', '')
                    
                    formatted = f"Title: {title}\nSummary: {content}...\nSource: {source}\n"
                    
                    is_vip = any(vip.lower() in source.lower() for vip in VIP_SOURCES)
                    if is_vip: vip_news.append(formatted)
                    else: regular_news.append(formatted)
        except: continue

    # Anti-Shuffle Logic (PENTING)
    final_news = list(dict.fromkeys(vip_news))
    
    # Isi kekurangan dengan berita reguler sampai total 5-6
    if len(final_news) < 6:
        needed = 6 - len(final_news)
        final_news.extend(list(dict.fromkeys(regular_news))[:needed])
        
    return final_news[:6] # KITA AMBIL 6 BERITA UTUH UNTUK AI

async def analyze_sentiment(news_list, symbol):
    if not news_list:
        return {'score': 0, 'reason': 'Tidak ada berita', 'headlines': []}
    
    # Simpan judul untuk ditampilkan di Main Menu
    headlines_debug = [n.split('\n')[0].replace("Title: ", "") for n in news_list]
    
    prompt = f"""
    Role: Senior Financial Analyst. 
    Task: Analyze news for {symbol} regarding Supply Chain & Demand.
    DATA: {chr(10).join(news_list)}
    INSTRUCTIONS:
    1. Identify KEY POSITIVE factors.
    2. Identify KEY NEGATIVE factors.
    3. WEIGH evidence.
    4. Score -10 to +10.
    5. Write 1-sentence summary.
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