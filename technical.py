import yfinance as yf
import pandas as pd
import os
import contextlib
from config import SMA_PERIOD, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD

def get_technical_analysis(symbol):
    try:
        with open(os.devnull, 'w') as fnull:
            with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                # Download data
                df = yf.download(tickers=symbol, period="6mo", interval="1d", progress=False)
        
        if df.empty or len(df) < 50: return None
        
        # Penanganan MultiIndex (Format baru yfinance)
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
            
        # Rename kolom biar standar
        df.rename(columns={'Close': 'close', 'Volume': 'volume', 'High': 'high', 'Low': 'low', 'Open': 'open'}, inplace=True)

        # --- 1. INDIKATOR UTAMA ---
        df['SMA'] = df['close'].rolling(SMA_PERIOD).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        rs = gain.rolling(RSI_PERIOD).mean() / loss.rolling(RSI_PERIOD).mean()
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist'] = df['MACD'] - df['Signal']

        # Volume
        df['Vol_Avg'] = df['volume'].rolling(20).mean()

        # --- 2. RISIKO: ATR (AVERAGE TRUE RANGE) ---
        # ATR mengukur volatilitas. Makin tinggi ATR, makin lebar Stop Loss-nya.
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(14).mean()

        # Support & Resistance Klasik (Low/High 20 hari terakhir)
        support_classic = df['low'].tail(20).min()
        resistance_classic = df['high'].tail(20).max()

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        # Deskripsi Tren
        trend = "UPTREND" if curr['close'] > curr['SMA'] else "DOWNTREND"
        
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
            'trend': trend,
            'rsi': float(curr['RSI']),
            'rsi_desc': rsi_desc,
            'macd_desc': macd_desc,
            'vol_desc': vol_desc,
            'support': float(support_classic),
            'resistance': float(resistance_classic),
            'atr': float(curr['ATR']) # Kita butuh ini untuk kalkulasi Stop Loss dinamis
        }
    except Exception as e:
        return None