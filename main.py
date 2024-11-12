# app.py
import asyncio
import websockets
import json
import aiohttp
import datetime

async def fetch_currency_rates():
    """Döviz kurlarını çeken fonksiyon"""
    async with aiohttp.ClientSession() as session:
        url = "https://api.exchangerate-api.com/v4/latest/TRY"
        async with session.get(url) as response:
            data = await response.json()
            return {
                'USD': 1/data['rates']['USD'],
                'EUR': 1/data['rates']['EUR'],
                'GBP': 1/data['rates']['GBP']
            }

async def send_currency_updates(websocket):
    """Websocket üzerinden döviz güncellemelerini gönderen fonksiyon"""
    try:
        while True:
            rates = await fetch_currency_rates()
            
            # Zaman damgası ekle
            rates['timestamp'] = datetime.datetime.now().strftime("%H:%M:%S")
            
            # Hesaplamalar
            rates['USD_EUR'] = rates['USD'] / rates['EUR']
            rates['EUR_GBP'] = rates['EUR'] / rates['GBP']
            
            await websocket.send(json.dumps(rates))
            await asyncio.sleep(5)  # 5 saniye bekle
    except websockets.exceptions.ConnectionClosed:
        pass

async def main():
    """Ana websocket sunucusu"""
    async with websockets.serve(send_currency_updates, "localhost", 8765):
        await asyncio.Future()  # Sonsuza kadar çalış

if __name__ == "__main__":
    asyncio.run(main())