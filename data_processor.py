import pandas as pd
from typing import Dict, List, Any
import logging
import re
import unicodedata
from database import get_db, Product, Variant, PriceHistory
from bs4 import BeautifulSoup
from datetime import datetime

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_text(text: str, max_length: int = 500) -> str:
    if not isinstance(text, str):
        text = str(text)
    # HTML etiketlerini temizle
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    text = ' '.join(text.split())
    return text[:max_length-3] + '...' if len(text) > max_length else text

def apply_price_markup(price: float, markup_percentage: float = 10.0) -> float:
    """
    Fiyata belirtilen yüzde kadar markup ekler
    """
    try:
        return price * (1 + markup_percentage / 100)
    except Exception as e:
        logger.error(f"Markup uygulama hatası: {str(e)}")
        return price

def clean_price(price_str: str) -> float:
    """
    Fiyat string'ini temizle ve float'a çevir
    Hata durumunda 0.0 döndür
    """
    try:
        if not isinstance(price_str, str):
            price_str = str(price_str)
        # Binlik ayracı olan noktaları kaldır
        cleaned = price_str.replace('.', '')
        # Virgülü noktaya çevir
        cleaned = cleaned.replace(',', '.')
        # Sadece sayısal değerleri ve noktayı tut
        cleaned = re.sub(r'[^\d.]', '', cleaned)
        # Float'a çevir
        base_price = float(cleaned) if cleaned else 0.0
        # %10 markup uygula
        return apply_price_markup(base_price) if base_price > 0 else 0.0
    except Exception as e:
        logger.warning(f"Fiyat temizleme hatası ({str(price_str)}): {str(e)}")
        return 0.0

def clean_handle(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    handle = text.lower().replace(' ', '-')
    handle = re.sub(r'[^a-z0-9-]', '', handle)
    handle = re.sub(r'-+', '-', handle)
    return handle.strip('-')

def format_properties_for_html(properties: dict) -> str:
    """
    Ürün özelliklerini HTML formatına dönüştürür
    """
    if not properties:
        return ""

    html = "<div class='product-properties'>\n"
    html += "<h3>Ürün Özellikleri</h3>\n"
    html += "<ul>\n"

    for key, value in properties.items():
        clean_key = clean_text(str(key), 100)
        clean_value = clean_text(str(value), 100)
        html += f"<li><strong>{clean_key}:</strong> {clean_value}</li>\n"

    html += "</ul>\n"
    html += "</div>"
    return html

def normalize_image_url(url: str) -> str:
    """Normalizes image URLs (add a simple example)."""
    # Add your normalization logic here.  This is a placeholder.
    return url if url else None


def process_data(raw_data: List[Dict[str, Any]], source_url: str) -> pd.DataFrame:
    logger.info("Veri işleme başladı")

    if not raw_data:
        logger.warning("İşlenecek veri bulunamadı")
        return pd.DataFrame()

    # Shopify için gerekli sütunlar
    columns = [
        'Handle', 'Title', 'Body (HTML)', 'Vendor', 'Type', 'Tags',
        'Published', 'Option1 Name', 'Option1 Value', 'Option2 Name',
        'Option2 Value', 'Option3 Name', 'Option3 Value', 'Variant SKU',
        'Variant Inventory Tracker', 'Variant Inventory Qty',
        'Variant Inventory Policy', 'Variant Fulfillment Service',
        'Variant Price', 'Variant Requires Shipping', 'Variant Taxable',
        'Image Src', 'Image Position', 'Image Alt Text', 'Status',
        'Database_ID', 'Properties'  # Özellikler için yeni sütun
    ]

    processed_rows = []
    for item in raw_data:
        title = item.get('title', '')
        if not title:
            logger.warning("Başlık bulunamadı, ürün atlanıyor")
            continue

        handle = clean_handle(title)
        base_price = clean_price(str(item.get('price', '0')))

        if base_price <= 0:
            logger.warning("Geçersiz fiyat: %s, ürün atlanıyor", str(base_price))
            continue

        # Ürün özellikleri
        properties = item.get('properties', {})
        properties_html = format_properties_for_html(properties)

        # Önce Product kaydını oluştur ve ID'yi al
        db = next(get_db())
        try:
            product = Product(
                title=title,
                description=properties_html,  # Açıklama yerine özellikleri kullan
                image_url=item.get('image_urls', [''])[0] if item.get('image_urls') else None,
                source_url=source_url,
                stock_status=item.get('stock_status', True)
            )
            db.add(product)
            db.flush()  # ID'yi almak için flush
            product_id = product.id

            # Variant kaydını oluştur
            variant = Variant(
                product_id=product_id,
                sku=handle,
                current_price=base_price,
                stock=100
            )
            db.add(variant)

            # Fiyat geçmişi kaydı
            platform = 'trendyol' if 'trendyol.com' in source_url else 'hepsiburada'
            price_history = PriceHistory(
                product_id=product_id,
                price=base_price,
                platform=platform,
                tracked_at=datetime.utcnow()
            )
            db.add(price_history)
            db.commit()

            # DataFrame için temel satırı oluştur
            base_row = dict.fromkeys(columns, '')
            base_row.update({
                'Handle': handle,
                'Title': title,
                'Body (HTML)': properties_html,  # Açıklama yerine özellikleri kullan
                'Vendor': item.get('brand', ''),
                'Type': 'Clothing',
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
                'Status': 'active',
                'Database_ID': product_id,  # Veritabanı ID'sini sakla
                'Properties': properties_html  # Özellikleri ayrı bir sütunda sakla
            })

            # Ana görsel
            if item.get('image_urls'):
                base_row.update({
                    'Image Src': normalize_image_url(item['image_urls'][0]),  # URL'yi normalize et
                    'Image Position': '1',
                    'Image Alt Text': clean_text(title, 255)
                })
                processed_rows.append(base_row)

                # Ek görseller için satırlar ekle
                for img_index, img_url in enumerate(item['image_urls'][1:], start=2):
                    img_row = dict.fromkeys(columns, '')
                    normalized_url = normalize_image_url(img_url)  # URL'yi normalize et
                    if normalized_url:  # Sadece geçerli URL'leri ekle
                        img_row.update({
                            'Handle': handle,
                            'Image Src': normalized_url,
                            'Image Position': str(img_index),
                            'Image Alt Text': f"{clean_text(title, 255)} - {img_index}",
                            'Database_ID': product_id
                        })
                        processed_rows.append(img_row)

        except Exception as e:
            logger.error(f"Ürün kayıt hatası: {str(e)}")
            db.rollback()
        finally:
            db.close()

    # DataFrame oluştur
    df = pd.DataFrame(processed_rows, columns=columns)
    return df