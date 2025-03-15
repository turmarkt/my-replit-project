from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class PriceHistory(db.Model):
    __tablename__ = 'price_history'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    tracked_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PriceHistory {self.product_id} - {self.price}>'

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(512))
    source_url = db.Column(db.String(512))
    stock_status = db.Column(db.Boolean, default=True)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    variants = db.relationship('Variant', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.title}>'

class Variant(db.Model):
    __tablename__ = 'variants'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    sku = db.Column(db.String(100))
    current_price = db.Column(db.Numeric(10, 2))
    stock_quantity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Variant {self.sku}>'

class CompetitorPrice(db.Model):
    __tablename__ = 'competitor_prices'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    competitor_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    url = db.Column(db.String(512))
    tracked_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CompetitorPrice {self.competitor_name} - {self.price}>'