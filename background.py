from PIL import Image

def create_simple_background(width=1920, height=1080, bg_color="#000000"):  # Siyah arka plan
    # Ana görsel oluştur
    image = Image.new('RGB', (width, height), bg_color)

    # Görüntüyü kaydet
    image.save('background.png')

if __name__ == "__main__":
    create_simple_background()