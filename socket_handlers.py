from fastapi import FastAPI
from fastapi_socketio import SocketManager
from fastapi.middleware.cors import CORSMiddleware
from forex_python.converter import CurrencyRates
import time

# terminalin arkaplan renkerlini ayarlayan ANSI kodları
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


app = FastAPI()

 
sio = SocketManager(app=app)
yukseltme2Sayi = 0  
yukseltme1Sayi = 0  


@app.get("/")
async def main():
    return {"message": "Hello World"}

@app.sio.on('join')
async def handle_join(sid, *args, **kwargs):
    print("Bağlantı gerçekleşti...")
    await sio.emit('lobby', 'User joined')

@sio.on('dolartl')
async def test(sid,*args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('USD', 'TRY')
    print(f"{birinciDeger} $ = {birinciDeger*rate} ₺")
    await sio.emit('dolartl', f"{birinciDeger} $ = {birinciDeger*rate} ₺")

@sio.on('tldolar')
async def test(sid,*args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('TRY', 'USD')
    print(f"{birinciDeger} ₺ = {birinciDeger*rate} $")
    await sio.emit('tldolar', f"{birinciDeger} ₺ = {birinciDeger*rate} $")

@sio.on('eurotl')
async def test(sid,*args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('EUR', 'TRY')
    print(f"{birinciDeger} € = {birinciDeger*rate} ₺")
    await sio.emit('eurotl', f"{birinciDeger} € = {birinciDeger*rate} ₺")

@sio.on('tleuro')
async def test(sid,*args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('TRY', 'EUR')
    print(f"{birinciDeger} ₺ = {birinciDeger*rate} €")
    await sio.emit('tleuro', f"{birinciDeger} ₺ = {birinciDeger*rate} €")

@sio.on('sterlintl')
async def test(sid,*args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('GBP', 'TRY')
    print(f"{birinciDeger} £ = {birinciDeger*rate} ₺")
    await sio.emit('sterlintl', f"{birinciDeger} £ = {birinciDeger*rate} ₺")

@sio.on('tlsterlin')
async def test(sid,*args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('TRY', 'GBP')
    print(f"{birinciDeger} ₺ = {birinciDeger*rate} £")
    await sio.emit('tlsterlin', f"{birinciDeger} ₺ = {birinciDeger*rate} £")

@sio.on('canliVeriOn')
async def test(sid,*args, **kwargs):
    print("Canlı veri alımı başladı...")
    c = CurrencyRates()
    dolartlrate = c.get_rate('USD', 'TRY')
    eurotlrate = c.get_rate('EUR', 'TRY')
    sterlintlrate = c.get_rate('GBP', 'TRY')
    tldolarrate = c.get_rate('TRY', 'USD')
    tleurorate = c.get_rate('TRY', 'EUR')
    tlsterlinrate = c.get_rate('TRY', 'GBP')
    await sio.emit('canliveriText', [dolartlrate,eurotlrate,sterlintlrate,tldolarrate,tleurorate,tlsterlinrate])

    




if __name__ == '__main__':
    import logging
    import sys

    logging.basicConfig(level=logging.DEBUG,
                        stream=sys.stdout)
    
    import uvicorn

    uvicorn.run("socket_handlers:app", host='127.0.0.1', port=8081, reload=True)