"""
Veritabanı modelleri.

Multi-tenancy: HER tabloda tenant_id var (tenants ve users hariç).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Float,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    plan: Mapped[str] = mapped_column(String(30), default="trial")
    active_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # LEGACY — artık kullanılmıyor (Paket 11c'de ürün bazlı sisteme geçildi)
    custom_design_keywords: Mapped[list] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    users: Mapped[list[User]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    stores: Mapped[list[Store]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    email_templates: Mapped[list[EmailTemplate]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    role: Mapped[str] = mapped_column(String(30), default="operator")
    permissions: Mapped[list] = mapped_column(JSONB, default=list)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_store_tenant_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    slug: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(30))

    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    matching_strategy: Mapped[str] = mapped_column(String(20), default="full")

    kisayollar_filename: Mapped[str | None] = mapped_column(String(100), nullable=True)
    badge_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="stores")
    shortcuts: Mapped[list[Shortcut]] = relationship(back_populates="store", cascade="all, delete-orphan")
    orders: Mapped[list[Order]] = relationship(back_populates="store", cascade="all, delete-orphan")
    designs: Mapped[list[Design]] = relationship(back_populates="store", cascade="all, delete-orphan")
    kisiye_ozel_products: Mapped[list[KisiyeOzelProduct]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )


class Shortcut(Base):
    """ESKİ — yeni mimaride Design tablosu kullanılır."""
    __tablename__ = "shortcuts"
    __table_args__ = (
        UniqueConstraint("store_id", "key", name="uq_shortcut_store_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    key: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    store: Mapped[Store] = relationship(back_populates="shortcuts")


# ═════════════════════════════════════════════════════════════════════
# DESIGN
# ═════════════════════════════════════════════════════════════════════

class Design(Base):
    __tablename__ = "designs"
    __table_args__ = (
        UniqueConstraint("store_id", "code", name="uq_design_store_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    file_path: Mapped[str] = mapped_column(String(500))
    file_format: Mapped[str] = mapped_column(String(10))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    product_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    product_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    kalip_tipi: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)

    birincil_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ikincil_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ucuncu_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)

    cmyk_hazirlanmis: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_kisiye_ozel: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    store: Mapped[Store] = relationship(back_populates="designs")


class KisiyeOzelProduct(Base):
    """Kişiye özel sayılacak Shopify ürünleri (Paket 11c)."""
    __tablename__ = "kisiye_ozel_products"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", name="uq_kop_store_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    product_id: Mapped[str] = mapped_column(String(50), index=True)
    product_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    product_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped[Store] = relationship(back_populates="kisiye_ozel_products")


class AccessoryProduct(Base):
    """Aksesuar olarak isaretlenen Shopify urunleri — kalip planina dahil edilmez."""
    __tablename__ = "accessory_products"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", name="uq_acc_store_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(String(50), index=True)
    product_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    product_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoupleProduct(Base):
    """Couple (cift kilif) urunleri — 2 ayri tasarim, ayni telefon modeline 2 birim."""
    __tablename__ = "couple_products"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", name="uq_couple_store_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(String(50), index=True)
    product_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    product_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    design_id_1: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("designs.id", ondelete="SET NULL"), nullable=True
    )
    design_id_2: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("designs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExternalCacheEntry(Base):
    __tablename__ = "external_cache"
    __table_args__ = (
        UniqueConstraint("tenant_id", "brand", "design_code", "phone_model",
                         name="uq_external_cache_canonical"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    brand: Mapped[str] = mapped_column(String(100))
    design_name: Mapped[str] = mapped_column(String(200))
    design_code: Mapped[str] = mapped_column(String(50))
    phone_model: Mapped[str] = mapped_column(String(100))
    variation: Mapped[str] = mapped_column(String(20), default="siyah")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ═════════════════════════════════════════════════════════════════════
# ORDER + LINE ITEM (Paket 12 ile genişletildi)
# ═════════════════════════════════════════════════════════════════════

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("store_id", "external_id", name="uq_order_store_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    external_id: Mapped[str] = mapped_column(String(50), index=True)
    order_number: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    fulfillment_status: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    financial_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at_platform: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)

    raw: Mapped[dict] = mapped_column(JSONB, default=dict)

    # ─── Paket 12: iş akışı alanları (server_default ile güvenli migration) ───
    current_stage: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False, index=True
    )
    is_acil: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False, index=True
    )
    is_tedarik_bekleme: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    is_hatali_gonderildi: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    is_iptal: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False, index=True
    )
    internal_lists: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    barkod_kodu: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped[Store] = relationship(back_populates="orders")
    line_items: Mapped[list[LineItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="LineItem.position"
    )
    status_history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order", cascade="all, delete-orphan",
        order_by="desc(OrderStatusHistory.created_at)",
    )
    customer_requests: Mapped[list[CustomerRequest]] = relationship(
        back_populates="order", cascade="all, delete-orphan",
        order_by="desc(CustomerRequest.created_at)",
    )
    email_logs: Mapped[list[EmailLog]] = relationship(
        back_populates="order", cascade="all, delete-orphan",
        order_by="desc(EmailLog.created_at)",
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    external_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    variant_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    title: Mapped[str] = mapped_column(Text)
    variant_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=1)
    position: Mapped[int] = mapped_column(Integer, default=0)

    properties: Mapped[list] = mapped_column(JSONB, default=list)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Kişiye özel atama (Paket 11b)
    assigned_design_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("designs.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    birincil_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ikincil_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ucuncu_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ─── Paket 12: üretim akışı alanları ───
    tedarik_status: Mapped[str] = mapped_column(
        String(20), default="bekliyor", server_default=text("'bekliyor'"), nullable=False
    )
    is_hazir: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    is_kaliba_eklendi: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    device_model_override: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # shopify_urun_gorseli

    order: Mapped[Order] = relationship(back_populates="line_items")
    assigned_design: Mapped[Design | None] = relationship("Design", foreign_keys=[assigned_design_id])


# ═════════════════════════════════════════════════════════════════════
# PAKET 12 — Yeni tablolar
# ═════════════════════════════════════════════════════════════════════

class OrderStatusHistory(Base):
    """Sipariş durum değişiklik geçmişi (görsel 3 'Durum Geçmişi')."""
    __tablename__ = "order_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    from_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(50))   # stage_change / acil / iptal / hatali / not vb.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="status_history")


class CustomerRequest(Base):
    """Müşteri talepleri (görsel 5 'Müşteri Talepleri')."""
    __tablename__ = "customer_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    request_type: Mapped[str] = mapped_column(String(50), default="genel")
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="acik", server_default=text("'acik'"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order] = relationship(back_populates="customer_requests")


class EmailTemplate(Base):
    """Şablonlu e-posta tanımları (görsel 6 'şablonlu e-posta')."""
    __tablename__ = "email_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_email_template_tenant_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    key: Mapped[str] = mapped_column(String(50))      # ör: kargoda, hatali_adres, tasarim_onay
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="email_templates")


class EmailLog(Base):
    """Gönderilen e-posta kaydı (görsel 5 'E-posta Geçmişi')."""
    __tablename__ = "email_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    template_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_email: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="gonderildi", server_default=text("'gonderildi'"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="email_logs")


# ═════════════════════════════════════════════════════════════════════
# PIPELINE (eski)
# ═════════════════════════════════════════════════════════════════════

class PipelineSession(Base):
    __tablename__ = "pipeline_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[str] = mapped_column(String(30), default="idle")
    letters: Mapped[str | None] = mapped_column(String(10), nullable=True)
    illustrator_output: Mapped[str] = mapped_column(Text, default="")
    raw_output: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list[PipelineItem]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class PipelineItem(Base):
    __tablename__ = "pipeline_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_sessions.id", ondelete="CASCADE"), index=True
    )

    order_num: Mapped[str] = mapped_column(String(50), index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(100))
    design: Mapped[str] = mapped_column(Text)
    renk: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kod: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    is_kisiye_ozel: Mapped[bool] = mapped_column(Boolean, default=False)
    yurtici: Mapped[bool] = mapped_column(Boolean, default=False)
    source_kisiye_order_num: Mapped[str | None] = mapped_column(String(50), nullable=True)

    model_group: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[PipelineSession] = relationship(back_populates="items")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=True)

    kind: Mapped[str] = mapped_column(String(40), default="sync")  # sync | error | info
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Mold(Base):
    __tablename__ = "molds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=True, index=True)

    kod: Mapped[str] = mapped_column(String(200), index=True)         # birlesik grup kodlari
    variation: Mapped[str] = mapped_column(String(20))               # SİYAH/BEYAZ/...
    kalip_kodlari: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # [A1,A5,B2]
    kilif_sayisi: Mapped[int] = mapped_column(Integer, default=0)
    rows_used: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="olusturuldu", server_default=text("'olusturuldu'"))  # olusturuldu | basildi | iptal

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    current_stage: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    pdf_indirilme_zamani: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_hatali: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Baskici Paneli: baski durumu (pipeline'dan bagimsiz)
    print_status: Mapped[str] = mapped_column(String(20), default="bekliyor", server_default=text("'bekliyor'"))  # bekliyor | basildi | eksik_var | hatali_basildi
    print_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    print_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    print_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["MoldItem"]] = relationship(back_populates="mold", cascade="all, delete-orphan")


class MoldItem(Base):
    __tablename__ = "mold_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    mold_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("molds.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    line_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("line_items.id", ondelete="SET NULL"), nullable=True)
    design_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("designs.id", ondelete="SET NULL"), nullable=True)

    slot_index: Mapped[int] = mapped_column(Integer, default=0)       # kalıptaki sıra (0..26)
    kalip_kodu: Mapped[str] = mapped_column(String(200))            # IPHONE-15-GROUP|SIYAH...
    design_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_hazir: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    mold: Mapped["Mold"] = relationship(back_populates="items")


class MoldStatusHistory(Base):
    __tablename__ = "mold_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    mold_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("molds.id", ondelete="SET NULL"), nullable=True, index=True)

    from_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(40))           # stage_change | hatali | iptal ...
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MoldTemplate(Base):
    __tablename__ = "mold_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(120), default="Varsayılan Kalıp")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # yüklenen şablon PDF
    page_w_pt: Mapped[float] = mapped_column(Float, default=0)
    page_h_pt: Mapped[float] = mapped_column(Float, default=0)
    cols: Mapped[int] = mapped_column(Integer, default=9)
    rows: Mapped[int] = mapped_column(Integer, default=3)
    box_count: Mapped[int] = mapped_column(Integer, default=0)
    boxes: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # [{x0,y0,x1,y1,w,h}]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AskiItem(Base):
    """Askı — hatalı üretilip dükkanda hazır bekleyen, yeniden üretilmeden gönderim
    yapılabilen ürünler. Eşleşme: design_id + model (variation opsiyonel)."""
    __tablename__ = "aski_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "store_id", "design_id", "model", "variation",
            name="uq_aski_design_model_var",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    design_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("designs.id", ondelete="CASCADE"), index=True
    )

    model: Mapped[str] = mapped_column(String(100), index=True)
    variation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_line_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("line_items.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PhoneModel(Base):
    """Telefon modeli olcu OVERLAY (baseline case_dimensions uzerine).
    tenant_id NULL -> global; doluysa tenant'a ozel. DB baseline'i ezer."""
    __tablename__ = "phone_models"
    __table_args__ = (
        UniqueConstraint("tenant_id", "spec_key", name="uq_phone_model_tenant_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    spec_key: Mapped[str] = mapped_column(String(60), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    brand: Mapped[str | None] = mapped_column(String(40), nullable=True)

    width_cm: Mapped[float] = mapped_column(Float)
    height_cm: Mapped[float] = mapped_column(Float)
    radius_cm: Mapped[float] = mapped_column(Float, default=0, server_default=text("0"))

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StockGroup(Base):
    """Stok ana kalemi (urun grubu). Or: 'Ekran Koruyucu'. Alt kalemler = StockItem (model bazli)."""
    __tablename__ = "stock_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_stock_group_tenant_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    # Bu gruba bagli Shopify urunleri (kargoda eslestirme icin): [{"store_id":..,"product_id":..,"title":..}]
    linked_products: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list["StockItem"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class StockItem(Base):
    """Fiziksel stok kalemi (tenant geneli). bos_kilif/ekran/lens/diger."""
    __tablename__ = "stock_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_stock_tenant_sku"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sku: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30), default="bos_kilif", server_default=text("'bos_kilif'"), index=True)
    variation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    # Coklu uyumlu model (ekran koruyucu/kilif birden cok modele uyar) — bu liste paylasimli tek stok
    models: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))

    quantity: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)

    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    variant_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    group: Mapped["StockGroup | None"] = relationship(back_populates="items")


class StockMovement(Base):
    """Stok hareketi (giris/cikis audit)."""
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    stock_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_items.id", ondelete="CASCADE"), index=True
    )

    delta: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(40))
    ref_mold_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ref_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrackerOrderStage(Base):
    """Public sipariş takip — siparişe atanan BERNZ ozel asamasi (mongo'dan port)."""
    __tablename__ = "tracker_order_stages"
    __table_args__ = (
        UniqueConstraint("shopify_order_id", name="uq_tracker_stage_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )
    shopify_order_id: Mapped[str] = mapped_column(String(50), index=True)
    order_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    stage_id: Mapped[str] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SupportThread(Base):
    """Public destek konuşması — bir siparişe bağlı (Paket 3)."""
    __tablename__ = "support_threads"
    __table_args__ = (
        UniqueConstraint("shopify_order_id", name="uq_support_thread_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )

    shopify_order_id: Mapped[str] = mapped_column(String(50), index=True)
    order_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    customer_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # acik = musteri yazdi, admin cevabi bekliyor | cevaplandi = admin son yazan | kapali
    status: Mapped[str] = mapped_column(
        String(20), default="acik", server_default=text("'acik'"), nullable=False, index=True
    )
    unread_admin: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_admin_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="SupportMessage.created_at"
    )


class SupportMessage(Base):
    """Destek konuşmasındaki tekil mesaj."""
    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_threads.id", ondelete="CASCADE"), index=True
    )
    sender: Mapped[str] = mapped_column(String(10))  # musteri | admin
    body: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # destek_gorsel
    is_read_by_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thread: Mapped["SupportThread"] = relationship(back_populates="messages")


class Dealer(Base):
    """Bayii — B2B musteri. Cari hesap + bilgi. Siparisleri sanal bir Store'a yazilir."""
    __tablename__ = "dealers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_dealer_tenant_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    # Bayinin siparislerinin yazildigi sanal store (platform='bayii')
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cari bakiye: pozitif = bayi bize borclu (alacagimiz), negatif = biz bayiye borcluyuz
    balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    # Bayi sabit birim fiyati (urun basina) + kargo ucreti (0 = yansitilmaz)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    shipping_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    transactions: Mapped[list["DealerTransaction"]] = relationship(
        back_populates="dealer", cascade="all, delete-orphan"
    )


class DealerTransaction(Base):
    """Bayii cari hareketi. tutar>0 borc (siparis), tutar<0 alacak/odeme."""
    __tablename__ = "dealer_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    dealer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id", ondelete="CASCADE"), index=True
    )

    # tutar: pozitif = bayinin borcu artar (siparis), negatif = odeme/alacak
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    kind: Mapped[str] = mapped_column(String(20))  # 'siparis' | 'odeme' | 'duzeltme'
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ref_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    balance_after: Mapped[float] = mapped_column(Numeric(12, 2))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dealer: Mapped["Dealer"] = relationship(back_populates="transactions")

