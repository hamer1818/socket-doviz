# app.py
import asyncio
import websockets
import json
import aiohttp
import datetime
from collections import deque

# Son 60 veri noktasını saklayacak geçmiş veri yapısı (5 saniyelik aralıklarla ~5 dakikalık veri)
currency_history = {
    'USD': deque(maxlen=60),
    'EUR': deque(maxlen=60),
    'GBP': deque(maxlen=60),
    'JPY': deque(maxlen=60),
    'CHF': deque(maxlen=60),
    'CAD': deque(maxlen=60),
    'AUD': deque(maxlen=60),
}

# Alarm seviyeleri
alarm_levels = {
    'USD': {'min': 0, 'max': float('inf')},
    'EUR': {'min': 0, 'max': float('inf')},
    'GBP': {'min': 0, 'max': float('inf')},
}

async def fetch_currency_rates():
    """Döviz kurlarını çeken fonksiyon"""
    async with aiohttp.ClientSession() as session:
        url = "https://api.exchangerate-api.com/v4/latest/TRY"
        async with session.get(url) as response:
            data = await response.json()
            return {
                'USD': 1/data['rates']['USD'],
                'EUR': 1/data['rates']['EUR'],
                'GBP': 1/data['rates']['GBP'],
                'JPY': 1/data['rates']['JPY'],
                'CHF': 1/data['rates']['CHF'],
                'CAD': 1/data['rates']['CAD'],
                'AUD': 1/data['rates']['AUD']
            }

def calculate_trend(currency):
    """Bir para birimi için trend analizi yapar"""
    if len(currency_history[currency]) < 2:
        return "sabit"
    
    # Son 10 veri noktası varsa onları kullan, yoksa tümünü
    data_points = list(currency_history[currency])[-10:]
    
    if len(data_points) >= 2:
        # Son değer ve 10 veri öncesinin değeri arasındaki fark
        change = data_points[-1] - data_points[0]
        percent_change = (change / data_points[0]) * 100
        
        if percent_change > 0.5:
            return "yükseliyor"
        elif percent_change < -0.5:
            return "düşüyor"
    
    return "sabit"

def check_alarms(rates):
    """Döviz kurları için alarm kontrolü yapar"""
    alarms = {}
    for currency, rate in rates.items():
        if currency in alarm_levels:
            if rate > alarm_levels[currency]['max']:
                alarms[currency] = 'high'
            elif rate < alarm_levels[currency]['min']:
                alarms[currency] = 'low'
    
    return alarms

def calculate_change(currency):
    """Bir para birimi için değişim yüzdesini hesaplar"""
    if len(currency_history[currency]) < 2:
        return {'change': 0, 'percent': 0}
    
    current = currency_history[currency][-1]
    previous = currency_history[currency][-2]
    
    change = current - previous
    percent = (change / previous) * 100 if previous != 0 else 0
    
    return {
        'change': change,
        'percent': percent
    }

async def send_currency_updates(websocket):
    """Websocket üzerinden döviz güncellemelerini gönderen fonksiyon"""
    try:
        while True:
            rates = await fetch_currency_rates()
            
            # Zaman damgası ekle
            timestamp = datetime.datetime.now()
            rates['timestamp'] = timestamp.strftime("%H:%M:%S")
            rates['date'] = timestamp.strftime("%Y-%m-%d")
            
            # Geçmiş verileri güncelle
            for currency, rate in rates.items():
                if currency in currency_history and currency not in ['timestamp', 'date']:
                    currency_history[currency].append(rate)
            
            # Hesaplamalar
            rates['USD_EUR'] = rates['USD'] / rates['EUR']
            rates['EUR_GBP'] = rates['EUR'] / rates['GBP']
            
            # Trend analizi
            trends = {currency: calculate_trend(currency) for currency in ['USD', 'EUR', 'GBP']}
            rates['trends'] = trends
            
            # Değişim yüzdeleri
            changes = {currency: calculate_change(currency) for currency in ['USD', 'EUR', 'GBP']}
            rates['changes'] = changes
            
            # Alarm kontrolü
            alarms = check_alarms(rates)
            if alarms:
                rates['alarms'] = alarms
            
            # Websockete verileri gönder
            await websocket.send(json.dumps(rates))
            await asyncio.sleep(5)  # 5 saniye bekle
    except websockets.exceptions.ConnectionClosed:
        pass

async def handle_client(websocket):
    """Client ile iletişim kuran ana fonksiyon"""
    # Client'dan komut dinleme
    client_task = asyncio.create_task(handle_client_commands(websocket))
    # Kur güncellemelerini gönderme
    update_task = asyncio.create_task(send_currency_updates(websocket))
    
    await asyncio.gather(client_task, update_task)

async def handle_client_commands(websocket):
    """Client'dan gelen komutları işler"""
    try:
        async for message in websocket:
            try:
                command = json.loads(message)
                
                if command['type'] == 'set_alarm':
                    currency = command['currency']
                    level_type = command['level_type']  # 'min' veya 'max'
                    level_value = command['value']
                    
                    if currency in alarm_levels:
                        alarm_levels[currency][level_type] = level_value
                        await websocket.send(json.dumps({
                            'type': 'alarm_set',
                            'currency': currency,
                            'level_type': level_type,
                            'value': level_value
                        }))
                
                elif command['type'] == 'get_history':
                    currency = command['currency']
                    if currency in currency_history:
                        history_data = list(currency_history[currency])
                        await websocket.send(json.dumps({
                            'type': 'history_data',
                            'currency': currency,
                            'data': history_data
                        }))
                    
            except json.JSONDecodeError:
                print("Hatalı JSON formatı")
            except KeyError:
                print("Eksik anahtar")
    except websockets.exceptions.ConnectionClosed:
        pass

async def main():
    """Ana websocket sunucusu"""
    server = await websockets.serve(handle_client, "localhost", 8765)
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())