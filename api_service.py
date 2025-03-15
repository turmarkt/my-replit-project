from flask import Flask, request, jsonify
from functools import wraps
import os
import jwt
from datetime import datetime, timedelta
from database import get_db, Product, PriceHistory
from scraper import scrape_website
import logging
from data_processor import clean_price

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-API-Token')
        if not token:
            return jsonify({'message': 'Token gerekli!'}), 401
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except:
            return jsonify({'message': 'Geçersiz token!'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/token', methods=['POST'])
def generate_token():
    """API token oluştur"""
    auth = request.authorization
    if auth and auth.username == os.environ.get('API_USERNAME') and \
       auth.password == os.environ.get('API_PASSWORD'):
        token = jwt.encode(
            {'user': auth.username, 'exp': datetime.utcnow() + timedelta(days=30)},
            app.config['SECRET_KEY'],
            algorithm="HS256"
        )
        return jsonify({'token': token})
    return jsonify({'message': 'Geçersiz kimlik bilgileri!'}), 401

@app.route('/api/products/update', methods=['POST'])
@token_required
def update_products():
    """Ürünleri güncelle"""
    try:
        db = next(get_db())
        products = db.query(Product).all()
        updated_count = 0
        failed_count = 0
        
        for product in products:
            try:
                # Ürün verilerini çek
                raw_data = scrape_website(product.source_url)
                if raw_data and len(raw_data) > 0:
                    # Fiyat güncelleme
                    new_price = clean_price(str(raw_data[0].get('price', 0)))
                    if new_price > 0:
                        # Fiyat geçmişine ekle
                        price_history = PriceHistory(
                            product_id=str(product.id),
                            price=new_price,
                            platform='trendyol' if 'trendyol.com' in product.source_url else 'hepsiburada',
                            tracked_at=datetime.utcnow()
                        )
                        db.add(price_history)
                        
                        # Ürün verilerini güncelle
                        product.title = raw_data[0].get('title', product.title)
                        product.description = raw_data[0].get('description', product.description)
                        product.image_url = raw_data[0].get('image_urls', [None])[0] or product.image_url
                        product.last_checked = datetime.utcnow()
                        
                        # Stok durumunu kontrol et
                        if 'stock_status' in raw_data[0]:
                            product.stock_status = raw_data[0]['stock_status']
                        
                        updated_count += 1
                    else:
                        failed_count += 1
                        logger.warning(f"Geçersiz fiyat: {product.source_url}")
                else:
                    failed_count += 1
                    logger.warning(f"Veri çekilemedi: {product.source_url}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Ürün güncelleme hatası ({product.source_url}): {str(e)}")
                continue
        
        db.commit()
        return jsonify({
            'message': 'Güncelleme tamamlandı',
            'updated': updated_count,
            'failed': failed_count
        })
    
    except Exception as e:
        logger.error(f"Genel güncelleme hatası: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/products/status', methods=['GET'])
@token_required
def get_product_status():
    """Ürün durumlarını getir"""
    try:
        db = next(get_db())
        products = db.query(Product).all()
        
        status_data = [{
            'id': product.id,
            'title': product.title,
            'stock_status': product.stock_status,
            'last_checked': product.last_checked.isoformat() if product.last_checked else None,
            'source_url': product.source_url
        } for product in products]
        
        return jsonify(status_data)
    except Exception as e:
        logger.error(f"Durum sorgulama hatası: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
