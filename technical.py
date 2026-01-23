import yfinance as yf
import pandas as pd
from config import SMA_PERIOD, EMA_PERIOD, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD

# --- FUNGSI CEK KESEHATAN PASAR ---
def get_market_overview():
    try:
        indices = ["^GSPC", "^IXIC"]
        market_mood = "NEUTRAL"
        market_score = 0
        
        # Download data (Tanpa Contextlib/Silencer)
        df = yf.download(tickers=indices, period="5d", interval="1d", progress=False)
        
        if df.empty:
            print("[DEBUG] Data Market Kosong.")
            return None
        
        # Handle MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            close_data = df['Close']
        else:
            close_data = df
            
        # Cek apakah kolom ada
        if '^IXIC' not in close_data.columns or '^GSPC' not in close_data.columns:
            return None

        # Analisa NASDAQ
        nasdaq_today = close_data['^IXIC'].iloc[-1]
        nasdaq_yest = close_data['^IXIC'].iloc[-2]
        nasdaq_change = ((nasdaq_today - nasdaq_yest) / nasdaq_yest) * 100
        
        # Analisa S&P 500
        sp500_today = close_data['^GSPC'].iloc[-1]
        sp500_yest = close_data['^GSPC'].iloc[-2]
        sp500_change = ((sp500_today - sp500_yest) / sp500_yest) * 100
        
        # Tentukan Mood
        if nasdaq_change > 1.0: 
            market_mood = "RISK ON (Bullish)"
            market_score = 2
        elif nasdaq_change > 0.2:
            market_mood = "POSITIVE"
            market_score = 1
        elif nasdaq_change < -1.5:
            market_mood = "RISK OFF (Crash/Fear)"
            market_score = -2
        elif nasdaq_change < -0.5:
            market_mood = "NEGATIVE"
            market_score = -1
        else:
            market_mood = "SIDEWAYS"
            market_score = 0
            
        return {
            'nasdaq_change': float(nasdaq_change),
            'sp500_change': float(sp500_change),
            'mood': market_mood,
            'score': market_score
        }
    except Exception as e:
        print(f"[DEBUG] Error Market Overview: {e}") # Print Error biar ketahuan
        return None

# --- FUNGSI ANALISA SAHAM ---
def get_technical_analysis(symbol):
    try:
        # Download Data (Tanpa Contextlib)
        df_daily = yf.download(tickers=symbol, period="1y", interval="1d", progress=False)
        df_weekly = yf.download(tickers=symbol, period="2y", interval="1wk", progress=False)
        
        if df_daily.empty:
            print(f"[DEBUG] Data Daily Kosong untuk {symbol}")
            return None
            
        if len(df_daily) < 50:
            print(f"[DEBUG] Data Kurang (<50 bar) untuk {symbol}")
            return None

        # Standarisasi Kolom
        if isinstance(df_daily.columns, pd.MultiIndex): df_daily.columns = df_daily.columns.get_level_values(0)
        df_daily.rename(columns={'Close': 'close', 'Volume': 'volume', 'High': 'high', 'Low': 'low', 'Open': 'open'}, inplace=True)

        if isinstance(df_weekly.columns, pd.MultiIndex): df_weekly.columns = df_weekly.columns.get_level_values(0)
        df_weekly.rename(columns={'Close': 'close'}, inplace=True)

        # Weekly Analysis
        df_weekly['SMA_50_W'] = df_weekly['close'].rolling(50).mean()
        curr_wk = df_weekly.iloc[-1]
        weekly_trend = "BULLISH (Major)" if curr_wk['close'] > curr_wk['SMA_50_W'] else "BEARISH (Major)"

        # Daily Analysis
        df_daily['EMA_20'] = df_daily['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
        df_daily['SMA_50'] = df_daily['close'].rolling(SMA_PERIOD).mean()
        
        delta = df_daily['close'].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        rs = gain.rolling(RSI_PERIOD).mean() / loss.rolling(RSI_PERIOD).mean()
        df_daily['RSI'] = 100 - (100 / (1 + rs))

        ema12 = df_daily['close'].ewm(span=12, adjust=False).mean()
        ema26 = df_daily['close'].ewm(span=26, adjust=False).mean()
        df_daily['MACD'] = ema12 - ema26
        df_daily['Signal'] = df_daily['MACD'].ewm(span=9, adjust=False).mean()
        df_daily['Hist'] = df_daily['MACD'] - df_daily['Signal']

        df_daily['Vol_Avg'] = df_daily['volume'].rolling(20).mean()
        
        high_low = df_daily['high'] - df_daily['low']
        high_close = (df_daily['high'] - df_daily['close'].shift()).abs()
        low_close = (df_daily['low'] - df_daily['close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df_daily['ATR'] = true_range.rolling(14).mean()

        support_classic = df_daily['low'].tail(20).min()
        resistance_classic = df_daily['high'].tail(20).max()

        curr = df_daily.iloc[-1]
        prev = df_daily.iloc[-2]

        # Trend Logic
        if curr['close'] > curr['EMA_20'] and curr['EMA_20'] > curr['SMA_50']:
            daily_trend = "STRONG UPTREND"
        elif curr['close'] < curr['EMA_20'] and curr['EMA_20'] > curr['SMA_50']:
            daily_trend = "CORRECTION (Pullback)"
        elif curr['close'] < curr['EMA_20'] and curr['EMA_20'] < curr['SMA_50']:
            daily_trend = "STRONG DOWNTREND"
        else:
            daily_trend = "SIDEWAYS / CHOPPY"

        rsi_desc = "NETRAL"
        if curr['RSI'] > RSI_OVERBOUGHT: rsi_desc = "MAHAL (Overbought)"
        if curr['RSI'] < RSI_OVERSOLD: rsi_desc = "DISKON (Oversold)"
        
        macd_desc = "NETRAL"
        if curr['Hist'] > 0 and prev['Hist'] < 0: macd_desc = "GOLDEN CROSS"
        elif curr['Hist'] < 0 and prev['Hist'] > 0: macd_desc = "DEATH CROSS"
        elif curr['Hist'] > 0: macd_desc = "POSITIF"
        else: macd_desc = "NEGATIF"

        vol_desc = "RENDAH"
        if curr['volume'] > curr['Vol_Avg']: vol_desc = "TINGGI (Valid)"

        return {
            'price': float(curr['close']),
            'daily_trend': daily_trend,
            'weekly_trend': weekly_trend,
            'ema_20': float(curr['EMA_20']),
            'sma_50': float(curr['SMA_50']),
            'rsi': float(curr['RSI']),
            'rsi_desc': rsi_desc,
            'macd_desc': macd_desc,
            'vol_desc': vol_desc,
            'atr': float(curr['ATR']),
            'support': float(support_classic),
            'resistance': float(resistance_classic)
        }
    except Exception as e:
        print(f"[DEBUG] Error Technical Analysis: {e}") # Print error
        return None