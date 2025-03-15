import streamlit as st
import asyncio
import base64
from io import StringIO
from scraper import scrape_website
import pandas as pd
import requests
from urllib.parse import urlparse

def is_valid_image_url(url: str) -> bool:
    """Görsel URL'sinin geçerli olup olmadığını kontrol et"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and \
               result.path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
    except:
        return False

def display_image_safely(url: str, width: int = 150):
    """Güvenli bir şekilde görseli göster"""
    try:
        if is_valid_image_url(url):
            st.image(url, width=width)
        else:
            st.warning(f"Geçersiz görsel URL'si: {url}")
    except Exception as e:
        st.error(f"Görsel yüklenirken hata oluştu: {str(e)}")

def clean_text(text, max_length):
    if not isinstance(text, str):
        text = str(text)
    text = text.replace('\n', ' ')
    text = ' '.join(text.split())
    return text[:max_length]

def convert_to_shopify_csv(data: dict) -> pd.DataFrame:
    """Ürün verisini Shopify CSV formatına dönüştür"""
    try:
        # Temel ürün verisi
        title = data.get('title', '').strip()  # Başlığı temizle
        handle = title.lower().replace(' ', '-').replace('/', '-').replace('&', 'and')
        base_price = data.get('price', 0)
        raw_category = data.get('category', 'Giyim')

        # Kategori dönüşümü
        category_mapping = {
            'Giyim': 'Clothing & Accessories > Women\'s Clothing',
            'Elbise': 'Clothing & Accessories > Women\'s Clothing > Dresses',
            'Ayakkabı': 'Shoes > Women\'s Shoes',
            'Çanta': 'Bags & Purses > Handbags',
            'Aksesuar': 'Jewelry & Accessories > Fashion Accessories',
            'Ev & Yaşam': 'Home & Living',
            'Elektronik': 'Electronics > Consumer Electronics',
            'Kozmetik': 'Health & Beauty > Personal Care',
            'Spor': 'Sports & Recreation > Athletic Clothing',
            'Çocuk': 'Kids & Baby > Children\'s Clothing',
            'Erkek': 'Clothing & Accessories > Men\'s Clothing',
            'Kitap': 'Books, Movies & Music > Books'
        }

        # Product Type mapping
        type_mapping = {
            'Giyim': 'Casual Wear',
            'Elbise': 'Dress',
            'Ayakkabı': 'Shoes',
            'Çanta': 'Handbag',
            'Aksesuar': 'Accessory',
            'Ev & Yaşam': 'Home Decor',
            'Elektronik': 'Electronic Device',
            'Kozmetik': 'Beauty Product',
            'Spor': 'Sportswear',
            'Çocuk': 'Kids Wear',
            'Erkek': 'Menswear',
            'Kitap': 'Book'
        }

        shopify_category = category_mapping.get(raw_category, 'Clothing & Accessories > General')
        product_type = type_mapping.get(raw_category, 'General')

        base_data = {
            'Handle': handle,
            'Title': title,
            'Body (HTML)': '',
            'Vendor': '',
            'Product Category': shopify_category,
            'Type': product_type,
            'Tags': clean_text(title.replace(' ', ', ').lower(), 255),
            'Published': 'TRUE',
            'Option1 Name': 'Title',
            'Option1 Value': 'Default Title',
            'Variant SKU': handle,
            'Variant Inventory Tracker': 'shopify',
            'Variant Inventory Qty': '100',
            'Variant Inventory Policy': 'deny',
            'Variant Fulfillment Service': 'manual',
            'Variant Price': str(base_price),
            'Variant Requires Shipping': 'TRUE',
            'Variant Taxable': 'TRUE',
            'Status': 'active'
        }

        rows = []

        # Ana ürün için görsel ekle
        if data.get('image_urls'):
            valid_images = [url for url in data['image_urls'] if is_valid_image_url(url)]
            if valid_images:
                base_data['Image Src'] = valid_images[0]
                base_data['Image Position'] = '1'
                base_data['Image Alt Text'] = clean_text(title, 255)
                rows.append(base_data)

                # Ek görseller için satırlar ekle
                for idx, image_url in enumerate(valid_images[1:], 2):
                    image_row = {
                        'Handle': handle,
                        'Image Src': image_url,
                        'Image Position': str(idx),
                        'Image Alt Text': f"{clean_text(title, 255)} - {idx}"
                    }
                    rows.append(image_row)
            else:
                rows.append(base_data)
        else:
            rows.append(base_data)

        # DataFrame oluştur
        df = pd.DataFrame(rows)
        required_columns = [
            'Handle', 'Title', 'Body (HTML)', 'Vendor', 'Product Category', 'Type', 'Tags',
            'Published', 'Option1 Name', 'Option1 Value',
            'Variant SKU', 'Variant Inventory Tracker',
            'Variant Inventory Qty', 'Variant Inventory Policy',
            'Variant Fulfillment Service', 'Variant Price',
            'Variant Requires Shipping', 'Variant Taxable',
            'Image Src', 'Image Position', 'Image Alt Text', 'Status'
        ]

        # Eksik sütunları boş değerlerle doldur
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''

        return df[required_columns]
    except Exception as e:
        st.error(f"CSV dönüştürme hatası: {str(e)}")
        return pd.DataFrame()

def get_csv_download_link(df: pd.DataFrame, filename: str) -> str:
    """DataFrame'i CSV dosyasına dönüştür ve indirme linki oluştur"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}" class="download-button">CSV Dosyasını İndir</a>'
    return href

def main():
    # Sayfa yapılandırması
    st.set_page_config(
        page_title="Turmarkt Veri Yazılımı",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Ana başlık ve indirme butonu için üst satır
    col_title, col_download = st.columns([2, 1])

    with col_title:
        st.title("Turmarkt Veri Yazılımı")

    # URL giriş alanı
    url = st.text_input(
        "Ürün URL'sini girin:",
        placeholder="https://www.trendyol.com/...",
        help="Analiz etmek istediğiniz ürünün linkini yapıştırın"
    )

    if url:
        with st.spinner("Veri çekiliyor..."):
            try:
                # Veri çek
                result = asyncio.run(scrape_website(url))

                if result and len(result) > 0:
                    data = result[0]

                    # CSV dönüşümü
                    df = convert_to_shopify_csv(data)

                    # İndirme butonunu sağ üst köşeye yerleştir
                    with col_download:
                        st.markdown(get_csv_download_link(df, "shopify_urun.csv"), unsafe_allow_html=True)

                    # Sol ve sağ kolonlar
                    col1, col2 = st.columns([1, 2])

                    with col1:
                        st.header("Ürün Görselleri")
                        if data.get('image_urls'):
                            valid_images = [url for url in data['image_urls'] if is_valid_image_url(url)]
                            if valid_images:
                                # Her satırda 2 görsel için kolonlar oluştur
                                for i in range(0, len(valid_images), 2):
                                    cols = st.columns(2)
                                    # İlk görsel
                                    with cols[0]:
                                        display_image_safely(valid_images[i], width=150)
                                    # İkinci görsel (eğer varsa)
                                    if i + 1 < len(valid_images):
                                        with cols[1]:
                                            display_image_safely(valid_images[i + 1], width=150)
                            else:
                                st.warning("Geçerli ürün görseli bulunamadı")
                        else:
                            st.warning("Ürün görseli bulunamadı")

                    with col2:
                        st.header("Ürün Detayları")
                        # Başlık
                        title = data.get('title', '').strip()
                        if len(title) > 100:
                            title = title[:97] + "..."
                        st.write(f"**Başlık:** {title}")

                        # Fiyat
                        price = data.get('price', 0)
                        if isinstance(price, (int, float)) and price > 0:
                            try:
                                price_int = int(price)
                                price_dec = int((price - price_int) * 100)
                                formatted_price = f"{price_int:,}".replace(",", ".") + f",{price_dec:02d}"
                                st.write(f"**Fiyat:** {formatted_price} ₺")
                            except Exception as e:
                                st.write(f"**Fiyat:** {price:.2f} ₺")
                        else:
                            st.write("**Fiyat:** Belirtilmemiş")

                    # CSV önizleme
                    st.header("CSV Önizleme")
                    preview_df = df.copy()
                    # URL'leri kısalt
                    if 'Image Src' in preview_df.columns:
                        preview_df['Image Src'] = preview_df['Image Src'].apply(lambda x: x[:50] + '...' if isinstance(x, str) and len(x) > 50 else x)
                    st.dataframe(preview_df)

                else:
                    st.error("Bu URL'den veri çekilemedi. Lütfen geçerli bir Trendyol ürün linki girdiğinizden emin olun.")

            except Exception as e:
                st.error(f"Hata: {str(e)}")

    # Footer
    st.markdown('<div style="text-align: center; color: gray; padding: 20px;">© 2024 Turmarkt</div>', unsafe_allow_html=True)

if __name__ == '__main__':
    main()