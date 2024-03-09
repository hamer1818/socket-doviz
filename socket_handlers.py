from fastapi import FastAPI
from fastapi_socketio import SocketManager
from fastapi.middleware.cors import CORSMiddleware
from forex_python.converter import CurrencyRates

# terminalin arkaplan renklerini ayarlayan ANSI kodları
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

# CORS politikalarını belirleme
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tüm kaynaklardan gelen isteklere izin ver
    allow_credentials=True,
    allow_methods=["*"],  # Tüm HTTP metodlarına izin ver
    allow_headers=["*"],  # Tüm HTTP başlıklarına izin ver
)

 
# SocketManager oluşturma
sio = SocketManager(app=app) 

# Ana sayfa
@app.get("/")
async def main():
    return {"message": "Hello World"}

# WebSocket bağlantı işlemleri
@sio.on('connect')
async def handle_connect(sid, environ, *args, **kwargs):
    print("Bağlantı gerçekleşti...")
    await sio.emit('lobby', 'User joined', room=sid)

# Döviz hesaplama işlemleri
@sio.on('dolartl')
async def handle_dolartl(sid, *args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('USD', 'TRY')
    print(f"{birinciDeger} $ = {birinciDeger*rate} ₺")
    await sio.emit('dolartl', f"{birinciDeger} $ = {birinciDeger*rate} ₺", room=sid)

# Diğer döviz hesaplama işlemleri
@sio.on('tldolar')
async def handle_tldolar(sid, *args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('TRY', 'USD')
    print(f"{birinciDeger} ₺ = {birinciDeger*rate} $")
    await sio.emit('tldolar', f"{birinciDeger} ₺ = {birinciDeger*rate} $", room=sid)

@sio.on('eurotl')
async def handle_eurotl(sid, *args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('EUR', 'TRY')
    print(f"{birinciDeger} € = {birinciDeger*rate} ₺")
    await sio.emit('eurotl', f"{birinciDeger} € = {birinciDeger*rate} ₺", room=sid)

@sio.on('tleuro')
async def handle_tleuro(sid, *args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('TRY', 'EUR')
    print(f"{birinciDeger} ₺ = {birinciDeger*rate} €")
    await sio.emit('tleuro', f"{birinciDeger} ₺ = {birinciDeger*rate} €", room=sid)

@sio.on('sterlintl')
async def handle_sterlintl(sid, *args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('GBP', 'TRY')
    print(f"{birinciDeger} £ = {birinciDeger*rate} ₺")
    await sio.emit('sterlintl', f"{birinciDeger} £ = {birinciDeger*rate} ₺", room=sid)

@sio.on('tlsterlin')
async def handle_tlsterlin(sid, *args, **kwargs):
    birinciDeger = args[0]
    c = CurrencyRates()
    rate = c.get_rate('TRY', 'GBP')
    print(f"{birinciDeger} ₺ = {birinciDeger*rate} £")
    await sio.emit('tlsterlin', f"{birinciDeger} ₺ = {birinciDeger*rate} £", room=sid)
    
# Canlı veri işlemleri
@sio.on('canliVeriOn')
async def handle_canliveri(sid, *args, **kwargs):
    print("Canlı veri alımı başladı...")
    c = CurrencyRates()
    dolartlrate = c.get_rate('USD', 'TRY')
    eurotlrate = c.get_rate('EUR', 'TRY')
    sterlintlrate = c.get_rate('GBP', 'TRY')
    tldolarrate = c.get_rate('TRY', 'USD')
    tleurorate = c.get_rate('TRY', 'EUR')
    tlsterlinrate = c.get_rate('TRY', 'GBP')
    await sio.emit('canliveriText', [dolartlrate,eurotlrate,sterlintlrate,tldolarrate,tleurorate,tlsterlinrate], room=sid)

    




# Uygulamayı çalıştırma
if __name__ == '__main__':
    import logging
    import sys

    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    
    import uvicorn

    uvicorn.run("socket_handlers:app", host='127.0.0.1', port=8081, reload=True)