from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Household(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    auth_version = db.Column(db.Integer, nullable=False, default=1)
    active = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def is_active(self):
        return self.active

    def get_id(self):
        return f"{self.id}:{self.auth_version}"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # First UI supports one household per user; schema migration required for a selector.
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    role = db.Column(db.String(12), nullable=False, default="member")
    active = db.Column(db.Boolean, nullable=False, default=True)
    user = db.relationship(User)
    household = db.relationship(Household)
    __table_args__ = (db.CheckConstraint("role IN ('owner', 'member')", name="membership_role"),)


class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    email = db.Column(db.String(254), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime)
    revoked_at = db.Column(db.DateTime)


class LoginThrottle(db.Model):
    key = db.Column(db.String(64), primary_key=True)
    failures = db.Column(db.Integer, nullable=False, default=0)
    blocked_until = db.Column(db.DateTime)


class HouseholdItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(60), nullable=False, default="Sonstiges")
    source = db.Column(db.String(60), nullable=False, default="Laden")
    unit = db.Column(db.String(20), nullable=False, default="Packung")
    default_quantity = db.Column(db.Integer, nullable=False, default=1)
    stock_status = db.Column(db.String(12), nullable=False, default="unknown")
    is_favorite = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    archived = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        db.CheckConstraint("default_quantity BETWEEN 1 AND 999", name="item_default_quantity"),
        db.CheckConstraint("stock_status IN ('unknown','available','low','empty')", name="item_stock_status"),
    )


class ShoppingNeed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("household_item.id"), unique=True, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    item = db.relationship(HouseholdItem)
    __table_args__ = (db.CheckConstraint("quantity BETWEEN 0 AND 999", name="need_quantity"),)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("household_item.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    request_id = db.Column(db.String(36), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    before_state = db.Column(db.JSON, nullable=False)
    after_state = db.Column(db.JSON, nullable=False)
    version_after = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    reversed_by_id = db.Column(db.Integer, db.ForeignKey("activity.id"))
    item = db.relationship(HouseholdItem)
    user = db.relationship(User)
    __table_args__ = (db.UniqueConstraint("household_id", "request_id", name="activity_request"),)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("household_item.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    brand = db.Column(db.String(100), nullable=False, default="")
    package_text = db.Column(db.String(80), nullable=False, default="")
    data_source = db.Column(db.String(24), nullable=False, default="manual")
    version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}
    item = db.relationship(HouseholdItem)


class ProductBarcode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    code = db.Column(db.String(14), nullable=False)
    gtin = db.Column(db.String(14), nullable=False)
    product = db.relationship(Product)
    __table_args__ = (db.UniqueConstraint("household_id", "gtin", name="barcode_household_gtin"),)


class CatalogCache(db.Model):
    # Public product suggestions only, never household identities or photos.
    key = db.Column(db.String(32), primary_key=True)
    payload = db.Column(db.JSON)
    expires_at = db.Column(db.DateTime, nullable=False)


class CatalogGate(db.Model):
    key = db.Column(db.String(20), primary_key=True)
    next_allowed_at = db.Column(db.DateTime, nullable=False)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    name_key = db.Column(db.String(240), nullable=False)
    aliases = db.Column(db.JSON, nullable=False, default=list, server_default=db.text("'[]'"))
    version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (db.UniqueConstraint("household_id", "name_key", name="category_household_name"),)


class PurchaseSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    name_key = db.Column(db.String(240), nullable=False)
    aliases = db.Column(db.JSON, nullable=False, default=list, server_default=db.text("'[]'"))
    version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (db.UniqueConstraint("household_id", "name_key", name="source_household_name"),)


class ItemSource(db.Model):
    item_id = db.Column(db.Integer, db.ForeignKey("household_item.id"), primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("purchase_source.id"), primary_key=True)
    source = db.relationship(PurchaseSource)


class ShopOffer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    source_id = db.Column(db.Integer, db.ForeignKey("purchase_source.id"), nullable=False)
    url = db.Column(db.String(1000), nullable=False, default="")
    shop_sku = db.Column(db.String(80), nullable=False, default="")
    units_per_pack = db.Column(db.Numeric(12, 3), nullable=False, default=1, server_default="1")
    preferred = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    product = db.relationship(Product)
    source = db.relationship(PurchaseSource)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        db.UniqueConstraint("product_id", "source_id", name="offer_product_source"),
        db.CheckConstraint("units_per_pack > 0 AND units_per_pack <= 999999", name="offer_pack_units"),
    )
