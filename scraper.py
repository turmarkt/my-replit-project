import logging
from typing import Dict, List, Any
import cloudscraper
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

# Loglama yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_image_url(url: str) -> str:
    """Normalize image URL to proper format"""
    if not url:
        return None

    # Remove query parameters
    url = url.split('?')[0]

    # Add domain if URL starts with /
    if url.startswith('/'):
        url = f"https://cdn.dsmcdn.com{url}"
    elif url.startswith('//'):
        url = f"https:{url}"

    # Verify URL format
    if not url.startswith(('http://', 'https://')):
        return None

    # Check if URL ends with valid image extension
    if not url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return None

    return url

def is_valid_trendyol_url(url: str) -> bool:
    """URL'nin geçerli bir Trendyol ürün linki olup olmadığını kontrol et"""
    try:
        # URL boş ise
        if not url:
            return False

        # URL'yi temizle
        url = url.strip().lower()

        # Trendyol domain kontrolü
        if 'trendyol.com' not in url:
            return False

        return True

    except Exception as e:
        logger.error(f"URL doğrulama hatası: {str(e)}")
        return False

def extract_title_from_html(soup: BeautifulSoup) -> str:
    """HTML'den başlık bilgisini çıkar"""
    try:
        # Başlık için tüm olası seçicileri dene
        title_selectors = [
            'h1.pr-new-br',
            'h1.product-name',
            'h1.title',
            'h1.detail-name',
            'h1[data-drroot]',
            'span.product-name',
            'span.title',
            'div.pr-in-w > span'
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()

        # Meta title'dan almayı dene
        meta_title = soup.find('meta', {'property': 'og:title'})
        if meta_title and meta_title.get('content'):
            return meta_title['content'].strip()

        # script'lerden başlık almayı dene
        scripts = soup.find_all('script', {'type': 'application/javascript'})
        for script in scripts:
            if script.string and 'window.__PRODUCT_DETAIL_APP_INITIAL_STATE__' in script.string:
                match = re.search(r'"name":"([^"]+)"', script.string)
                if match:
                    return match.group(1)

        return ""
    except Exception as e:
        logger.error(f"Başlık çıkarma hatası: {str(e)}")
        return ""

def extract_price_from_html(soup: BeautifulSoup) -> float:
    """HTML'den fiyat bilgisini çıkar"""
    try:
        # Fiyat için tüm olası seçicileri dene
        price_selectors = [
            'span.prc-dsc',
            'span.price-new',
            'span.product-price',
            'span[data-price]',
            'span.prc-slg',
            'div.pr-in-w > div.pr-in-cn > div.pr-bx-w > div.pr-bx-dsc > span.prc-dsc',
            'div.featured-prices > span.featured-prices_first'
        ]

        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text().strip()
                # Sayısal olmayan karakterleri kaldır
                price_text = ''.join(c for c in price_text if c.isdigit() or c in '.,')
                # Binlik ayracı olan noktaları kaldır
                price_text = price_text.replace('.', '')
                # Virgülü noktaya çevir
                price_text = price_text.replace(',', '.')

                if price_text and float(price_text) > 0:
                    # %10 markup ekle
                    price = float(price_text) * 1.10
                    # En fazla 2 ondalık basamak
                    return round(price, 2)

        # Script'lerden fiyat almayı dene
        scripts = soup.find_all('script', {'type': 'application/javascript'})
        for script in scripts:
            if script.string and 'window.__PRODUCT_DETAIL_APP_INITIAL_STATE__' in script.string:
                match = re.search(r'"price":(\d+\.?\d*)', script.string)
                if match:
                    price = float(match.group(1))
                    return round(price * 1.10, 2)

        return 0.0
    except Exception as e:
        logger.error(f"Fiyat çıkarma hatası: {str(e)}")
        return 0.0

def extract_images_from_html(soup: BeautifulSoup) -> List[str]:
    """HTML'den görsel URL'lerini çıkar"""
    try:
        images = []
        # Tüm olası görsel seçicileri
        img_selectors = [
            'img.detail-section-img',
            'img.product-image',
            'img.gallery-image',
            'img.detail-image',
            'img[data-src]',
            'div.gallery-modal-content img',
            'div.product-slide img',
            'div.base-product-image img',
            'div.gallery-modal img',
            'div.image-container img',
            'img.ph-image',
            '.slider-content img'
        ]

        # HTML'den görselleri çek
        for selector in img_selectors:
            elements = soup.select(selector)
            for img in elements:
                # Tüm olası kaynak attributelerini kontrol et
                for attr in ['src', 'data-src', 'data-original', 'data-lazy', 'data-zoom-image']:
                    src = img.get(attr)
                    if src:
                        normalized_url = normalize_image_url(src)
                        if normalized_url and normalized_url not in images:
                            images.append(normalized_url)

        # Script'lerden görselleri çek
        scripts = soup.find_all('script', {'type': ['application/javascript', 'text/javascript']})
        for script in scripts:
            if script.string:
                # JSON veri yapısını bulmaya çalış
                patterns = [
                    r'window\.__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*({.*?});',
                    r'window\.__PRODUCT_DATA__\s*=\s*({.*?});',
                    r'window\.__INITIAL_STATE__\s*=\s*({.*?});'
                ]

                for pattern in patterns:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            # Farklı JSON yapılarını kontrol et
                            possible_paths = [
                                ['product', 'images'],
                                ['product', 'imageList'],
                                ['product', 'media', 'images'],
                                ['images'],
                                ['imageList']
                            ]

                            for path in possible_paths:
                                current = data
                                for key in path:
                                    if isinstance(current, dict) and key in current:
                                        current = current[key]
                                    else:
                                        current = None
                                        break

                                if current and isinstance(current, (list, dict)):
                                    if isinstance(current, dict):
                                        current = current.values()

                                    for item in current:
                                        if isinstance(item, str):
                                            url = item
                                        elif isinstance(item, dict):
                                            url = item.get('url') or item.get('src') or item.get('imageUrl')
                                        else:
                                            continue

                                        if url and isinstance(url, str):
                                            normalized_url = normalize_image_url(url)
                                            if normalized_url and normalized_url not in images:
                                                images.append(normalized_url)
                        except json.JSONDecodeError:
                            continue

        # En az 1 görsel yoksa hata logla
        if not images:
            logger.warning("Hiç görsel bulunamadı")
            return []

        return images[:8]  # En fazla 8 görsel al

    except Exception as e:
        logger.error(f"HTML'den görsel çıkarma hatası: {str(e)}")
        return []

def extract_category_from_html(soup: BeautifulSoup) -> str:
    """HTML'den kategori bilgisini çıkar"""
    try:
        # Breadcrumb'dan kategori almayı dene
        breadcrumb = soup.find('div', {'class': ['breadcrumb', 'product-categories']})
        if breadcrumb:
            links = breadcrumb.find_all('a')
            if links:
                return links[-1].get_text().strip()

        # Script'lerden kategori almayı dene
        scripts = soup.find_all('script', {'type': 'application/javascript'})
        for script in scripts:
            if script.string and 'window.__PRODUCT_DETAIL_APP_INITIAL_STATE__' in script.string:
                category_match = re.search(r'"categoryName":"([^"]+)"', script.string)
                if category_match:
                    return category_match.group(1)

        return 'Giyim'  # Varsayılan kategori
    except Exception as e:
        logger.error(f"Kategori çıkarma hatası: {str(e)}")
        return 'Giyim'

async def scrape_website(url: str) -> List[Dict[str, Any]]:
    """Trendyol'dan ürün verisi çek"""
    try:
        if not is_valid_trendyol_url(url):
            logger.error(f"Geçersiz Trendyol URL'si: {url}")
            return []

        # URL'yi düzenle
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Scraper oluştur
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )

        # İstek başlıkları
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr,en-US;q=0.7,en;q=0.3',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1'
        }

        try:
            response = scraper.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"Sayfa yüklenemedi: HTTP {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Sayfa yükleme hatası: {str(e)}")
            return []

        # HTML parse et
        soup = BeautifulSoup(response.text, 'html.parser')

        # Başlık bul
        title = extract_title_from_html(soup)
        if not title:
            logger.error("Başlık bulunamadı")
            return []

        # Fiyat bilgisini çek
        price = extract_price_from_html(soup)
        if price <= 0:
            logger.error("Geçerli fiyat bulunamadı")
            return []

        # Görsel ve kategori bilgilerini çek
        image_urls = extract_images_from_html(soup)
        category = extract_category_from_html(soup)

        # Sonuç oluştur
        product_data = {
            'title': title,
            'price': price,
            'image_urls': image_urls,
            'properties': {},
            'category': category
        }

        logger.info("Veri başarıyla çıkarıldı")
        return [product_data]

    except Exception as e:
        logger.error(f"Scraping hatası: {str(e)}")
        return []