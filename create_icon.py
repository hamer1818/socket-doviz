from PIL import Image
import os

# images klasörünün varlığını kontrol et
if not os.path.exists("images"):
    os.makedirs("images")

# JPEG dosyasını açın
try:
    img = Image.open("images/doviz.jpeg")
    
    # ICO formatına dönüştür ve kaydet
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save("images/doviz.ico", sizes=icon_sizes)
    print("Ikon dosyası başarıyla oluşturuldu: images/doviz.ico")
except FileNotFoundError:
    # Dosya bulunamazsa, basit bir ikon oluştur
    img = Image.new('RGB', (256, 256), color=(0, 120, 212))
    img.save("images/doviz.ico")
    print("JPEG dosyası bulunamadı, varsayılan ikon oluşturuldu: images/doviz.ico")
except Exception as e:
    print(f"Hata oluştu: {e}")