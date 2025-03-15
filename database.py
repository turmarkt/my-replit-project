from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import QueuePool
import os
from datetime import datetime
import logging
import time
from typing import Generator

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Veritabanı bağlantısı
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Bağlantı havuzu yapılandırması
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    properties = Column(Text)  # JSON string olarak saklanacak
    image_url = Column(Text)
    source_url = Column(Text)
    stock_status = Column(Boolean, default=True)  # Stock status field added
    last_checked = Column(DateTime, default=datetime.utcnow)  # Last checked field added
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    variants = relationship("Variant", back_populates="product", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    competitor_prices = relationship("CompetitorPrice", back_populates="product", cascade="all, delete-orphan")

class Variant(Base):
    __tablename__ = "variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    sku = Column(Text, nullable=True)
    size = Column(String(50), nullable=True)
    color = Column(String(50), nullable=True)
    stock = Column(Integer, default=0)
    current_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="variants")

class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    price = Column(Float, nullable=False)
    platform = Column(String(50), nullable=False)  # Platform bilgisi eklendi
    tracked_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="price_history")

class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    image_url = Column(Text, nullable=False)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="images")

class CompetitorPrice(Base):
    __tablename__ = "competitor_prices"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    competitor_name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    url = Column(Text)
    tracked_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="competitor_prices")

def init_db(max_retries: int = 3, retry_delay: int = 5) -> None:
    """Veritabanı tablolarını oluştur"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Veritabanı tabloları oluşturuluyor (Deneme {attempt + 1}/{max_retries})...")
            Base.metadata.create_all(bind=engine)
            logger.info("Veritabanı tabloları başarıyla oluşturuldu!")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Veritabanı oluşturma hatası (Deneme {attempt + 1}): {str(e)}")
                logger.info(f"{retry_delay} saniye sonra tekrar denenecek...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Veritabanı oluşturma başarısız oldu: {str(e)}")
                raise

def get_db() -> Generator:
    """Veritabanı oturumu oluştur ve yönet"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Veritabanı oturum hatası: {str(e)}")
        db.rollback()
        raise
    finally:
        try:
            db.close()
        except Exception as e:
            logger.error(f"Veritabanı oturumu kapatma hatası: {str(e)}")