from database import init_db
import logging

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        init_db()
        logger.info("Veritabanı tabloları başarıyla oluşturuldu!")
    except Exception as e:
        logger.error(f"Veritabanı oluşturma hatası: {str(e)}")
        raise