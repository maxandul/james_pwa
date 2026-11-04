from datetime import datetime, timezone
from uuid import uuid4

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Household(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    settings = db.Column(db.JSON, nullable=False, default=dict, server_default=db.text("'{}'"))
    version = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    __mapper_args__ = {'version_id_col': version}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    auth_version = db.Column(db.Integer, nullable=False, default=1)
    active = db.Column(db.Boolean, nullable=False, default=True)

    preferences = db.Column(db.JSON, nullable=False, default=dict, server_default=db.text("'{}'"))
    version = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    __mapper_args__ = {'version_id_col': version}

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
    version = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    __mapper_args__ = {'version_id_col': version}
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
    recipe_context = db.Column(db.JSON, nullable=False, default=list, server_default=db.text("'[]'"))
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
    active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    name_key = db.Column(db.String(240), nullable=False)
    aliases = db.Column(db.JSON, nullable=False, default=list, server_default=db.text("'[]'"))
    version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (db.UniqueConstraint("household_id", "name_key", name="category_household_name"),)


class PurchaseSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
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


class ReceiptImport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    fingerprint = db.Column(db.String(64), nullable=False)
    text_digest = db.Column(db.String(64), nullable=False)
    text = db.Column(db.Text, nullable=False)
    rows = db.Column(db.JSON, nullable=False)
    state = db.Column(db.String(12), nullable=False, default="draft")
    activity_ids = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    confirmed_at = db.Column(db.DateTime)
    __table_args__ = (
        db.UniqueConstraint("household_id", "fingerprint", name="receipt_household_fingerprint"),
        db.UniqueConstraint("household_id", "text_digest", name="receipt_household_text"),
        db.CheckConstraint("state IN ('draft','confirmed','reversed')", name="receipt_state"),
    )


class PurchasePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("household.id"), nullable=False, index=True)
    source_id = db.Column(db.Integer, db.ForeignKey("purchase_source.id"), nullable=False)
    request_id = db.Column(db.String(36), nullable=False)
    lines = db.Column(db.JSON, nullable=False)
    state = db.Column(db.String(12), nullable=False, default="draft")
    reference = db.Column(db.String(100), nullable=False, default="")
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    source = db.relationship(PurchaseSource)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        db.UniqueConstraint("household_id", "request_id", name="plan_household_request"),
        db.CheckConstraint("state IN ('draft','ordered','closed','cancelled')", name="plan_state"),
    )


class ChatConversation(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ChatTurn(db.Model):
    conversation_id = db.Column(db.String(36), db.ForeignKey('chat_conversation.id'), index=True)
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    auth_version = db.Column(db.Integer, nullable=False)
    request_id = db.Column(db.String(36), nullable=False)
    prompt = db.Column(db.String(2000), nullable=False)
    reply = db.Column(db.Text, nullable=False, default='')
    state = db.Column(db.String(12), nullable=False, default='running')
    actions = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'request_id', name='chat_user_request'),
        db.CheckConstraint("state IN ('running','done','failed')", name='chat_turn_state'),
    )


class ShopLogin(db.Model):
    """Private API-session references only. Never credentials or model/browser output."""
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    start_request_id = db.Column(db.String(36), nullable=False, default=lambda: str(uuid4()))
    active_user_id = db.Column(db.Integer, unique=True,
        default=lambda context: context.get_current_parameters()['user_id'])
    active_household_id = db.Column(db.Integer, unique=True,
        default=lambda context: context.get_current_parameters()['household_id'])
    cost_authorized_at = db.Column(db.DateTime)
    creation_started_at = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    auth_version = db.Column(db.Integer, nullable=False)
    session_id = db.Column(db.String(128), unique=True)
    request_id = db.Column(db.String(128))
    turn_id = db.Column(db.String(128))
    state = db.Column(db.String(20), nullable=False, default='creating')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    challenge_expires_at = db.Column(db.DateTime)
    outcome = db.Column(db.String(32))
    error_category = db.Column(db.String(32))
    http_status = db.Column(db.Integer)
    browser_calls = db.Column(db.Integer)
    auth_progress = db.Column(db.String(24))
    task_kind = db.Column(db.String(16), nullable=False, default='login', server_default='login')
    agent_report = db.Column(db.String(32))
    device_verified_at = db.Column(db.DateTime)
    __table_args__ = (db.CheckConstraint("task_kind IN ('login','cart')", name='shop_login_task_kind'),
        db.UniqueConstraint('user_id', 'start_request_id', name='shop_login_user_start'),
        db.CheckConstraint(
        "state IN ('queued','creating','running','pending','submitting','accepted','cancelled','unknown','closed','cleanup_pending')",
        name='shop_login_state'),)


class ShoppingView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    source_id = db.Column(db.Integer, db.ForeignKey('purchase_source.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    category_ids = db.Column(db.JSON, nullable=False, default=list, server_default=db.text("'[]'"))
    category_order = db.Column(db.JSON, nullable=False, default=list, server_default=db.text("'[]'"))
    item_sort = db.Column(db.String(20), nullable=False, default='name', server_default='name')
    is_default = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    version = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    source = db.relationship(PurchaseSource)
    __mapper_args__ = {'version_id_col': version}
    __table_args__ = (db.CheckConstraint("item_sort IN ('name','name_desc','favorites')", name='shopping_view_sort'),)


class RecipeCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    name_key = db.Column(db.String(240), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {'version_id_col': version}
    __table_args__ = (db.UniqueConstraint('household_id', 'name_key', name='recipe_category_household_name'),)


class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('recipe_category.id'), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    servings = db.Column(db.Numeric(10, 3), nullable=False, default=4)
    yield_unit = db.Column(db.String(30), nullable=False, default='Portionen')
    prep_minutes = db.Column(db.Integer, nullable=False, default=0)
    cook_minutes = db.Column(db.Integer, nullable=False, default=0)
    rest_minutes = db.Column(db.Integer, nullable=False, default=0)
    steps = db.Column(db.JSON, nullable=False, default=list)
    tags = db.Column(db.JSON, nullable=False, default=list)
    source = db.Column(db.String(1000), nullable=False, default='')
    is_favorite = db.Column(db.Boolean, nullable=False, default=False)
    image = db.Column(db.LargeBinary)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    version = db.Column(db.Integer, nullable=False, default=1)
    category = db.relationship(RecipeCategory)
    author = db.relationship(User, foreign_keys=[updated_by])
    ingredients = db.relationship('RecipeIngredient', cascade='all, delete-orphan', order_by='RecipeIngredient.position')
    notes = db.relationship('RecipeNote', cascade='all, delete-orphan', order_by='RecipeNote.created_at.desc()')
    __mapper_args__ = {'version_id_col': version}
    __table_args__ = (db.CheckConstraint('servings > 0', name='recipe_servings'),)


class RecipeIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('household_item.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(12, 3))
    unit = db.Column(db.String(30), nullable=False, default='')
    group = db.Column(db.String(60), nullable=False, default='')
    detail = db.Column(db.String(160), nullable=False, default='')
    is_staple = db.Column(db.Boolean, nullable=False, default=False)
    item = db.relationship(HouseholdItem)
    __table_args__ = (db.CheckConstraint('amount IS NULL OR amount > 0', name='recipe_ingredient_amount'),)


class RecipeNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    author = db.relationship(User)


class CookingAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False, index=True)
    request_id = db.Column(db.String(36), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    __table_args__ = (db.UniqueConstraint('household_id', 'request_id', name='cooking_action_request'),)
