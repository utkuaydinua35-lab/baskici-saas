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
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
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
    # Yeni self-servis kayıtlar yönetici onayı bekler; onaylanana kadar giriş yapılamaz.
    is_approved: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # White-label markalama: accent renk (#rrggbb) + uygulama adı (None ise name).
    brand_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    app_name: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # LEGACY — artık kullanılmıyor (Paket 11c'de ürün bazlı sisteme geçildi)
    custom_design_keywords: Mapped[list] = mapped_column(JSONB, default=list)

    # AI destek yaniti (Faz 3): acik/kapali + model secimi (haiku|sonnet|opus).
    # Model degisikligi master password ister (settings router). Yalnizca yonetici.
    ai_reply_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    ai_reply_model: Mapped[str] = mapped_column(
        String(20), default="opus", server_default=text("'opus'"), nullable=False
    )

    # Toplu takip: bu tarihten ONCE kargoya verilmis gonderiler "takip bekleyen"
    # listesinde gosterilmez. Sisteme gecmeden onceki birikmis gonderilerin
    # listeyi doldurmasini engeller. NULL = tumu gosterilir.
    takip_baslangic: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

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
    # Platform sahibi (cross-tenant): tüm atölyeleri yönetir (white-label kiralama).
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 2FA (TOTP / authenticator app). Secret Fernet ile şifreli saklanır,
    # backup_codes bcrypt hash'li liste. totp_enabled=False iken login zorlamaz.
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    totp_backup_codes: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)

    # Kayıt anı meta — self-servis kayıtta sahte/kötü niyetli hesabı ayıklamak için.
    # (Tarayıcı "bilgisayar adı"nı vermez; en fazla IP + User-Agent alınabilir.)
    signup_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signup_user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # Yalnızca geçiş anahtarı (passkey) ile giriş. True iken e-posta+şifre girişi
    # REDDEDİLİR -> şifre tahmini (brute-force) tamamen anlamsızlaşır.
    # Kilitlenmeye karşı: en az 1 passkey yoksa açılamaz; sunucudan geri alınabilir
    # (UPDATE users SET password_login_disabled=false WHERE email='...').
    password_login_disabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

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
    variant_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)  # coklu varyasyon: belirli varyant tasarimi
    variant_title: Mapped[str | None] = mapped_column(String(200), nullable=True)  # ornek: "Black" / "Red"

    kalip_tipi: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)

    birincil_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ikincil_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ucuncu_renk: Mapped[str | None] = mapped_column(String(30), nullable=True)

    cmyk_hazirlanmis: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_kisiye_ozel: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # True = tasarımın dosyası temiz baskı dosyası DEĞİL (ör. hazır mockup/kılıflı görsel).
    # Kalıp/baskı akışına girmez; temiz baskı dosyası yüklenince False olur.
    baski_dosyasi_yok: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

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
    # True ise tasarımlar sabit değil; sipariş başına kişiye özel olarak yüklenir
    # (line item assigned_design_id + assigned_design_id_2 / device_model_override(_2)).
    is_kisiye_ozel: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
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
    # Shopify "Arşivle" (closed_at): sipariş tamamlanmış/kapatılmış sayılır — fulfill
    # edilmese bile açık/acil listelerine girmemeli.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

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
    # Kullanici tarafindan kalip olusturucuya dahil edilmesin diye isaretlendi
    kalip_haric: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False, index=True
    )
    internal_lists: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    barkod_kodu: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Yorum daveti e-postası (teslimden N gün sonra) — sipariş başına TEK sefer
    review_invite_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Telafiler: hatali model/yanlis hazirlama yuzunden tekrar gonderilecek siparisler ───
    is_telafi: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False, index=True
    )
    # Klonlanan telafilerin kaynak (orijinal) siparisi; elle girilen telafilerde None,
    # sonradan normal siparisle eslestirilebilir.
    telafi_kaynak_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    telafi_sebep: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Soft-delete: dolu ise silinmis sayilir (geri alinabilir). Global ORM filtresi
    # (database.py do_orm_execute) silinmisleri otomatik gizler; cop/restore opt-out eder.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Kargo soz tarihi (SLA): bu tarihe kadar kargoya verilmeli. store.config.sla_days'ten
    # created_at_platform + sla_days olarak hesaplanir; elle override edilebilir (sync ezmez).
    kargo_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Basit Kargo gönderi referansı: {provider, id, barcode, takip_no, handler_code,
    # handler_name, status}. Re-print (etiket), iptal ve webhook eşleşmesi için.
    kargo_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ─── e-Fatura / e-Arşiv ───────────────────────────────────────────
    # Faturayı ENTEGRATÖR keser (GİB'e iletim mali mühür ister); biz yalnız
    # sipariş verisini sunar ve sonucu buraya yazarız.
    # durum: None (henüz yok) | beklemede | kesildi | hata | iptal
    fatura_durum: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    # {no, ettn, tarih, pdf_url, kaynak, hata} — entegratörün döndürdüğü bilgi
    fatura: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    store: Mapped[Store] = relationship(back_populates="orders")
    line_items: Mapped[list[LineItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="LineItem.position"
    )
    # Telafi self-ref: bir normal siparisin ona bagli telafileri (telafiler),
    # bir telafinin kaynak siparisi (telafi_kaynak).
    telafiler: Mapped[list["Order"]] = relationship(
        "Order", back_populates="telafi_kaynak",
        foreign_keys=[telafi_kaynak_order_id],
    )
    telafi_kaynak: Mapped["Order | None"] = relationship(
        "Order", back_populates="telafiler",
        foreign_keys=[telafi_kaynak_order_id], remote_side=[id],
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
    approvals: Mapped[list["DesignApproval"]] = relationship(
        back_populates="order", cascade="all, delete-orphan",
        order_by="desc(DesignApproval.created_at)",
    )
    shipments: Mapped[list["OrderShipment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan",
        order_by="OrderShipment.created_at",
    )


class OrderShipment(Base):
    """Kısmi kargolama — bir siparişin parça parça gönderilmesi.

    Shopify'daki "fulfillment" karşılığı: hangi kalemlerden kaç adedi hangi
    takip numarasıyla gitti. Sipariş TAMAMEN gönderildiğinde çağıran akış
    aşamayı kargoda'ya çeker; o ana kadar sipariş açık kalır.

    kargo_info (tek gönderi alanı) DOKUNULMAZ — Basit Kargo entegrasyonu,
    webhook eşleşmesi ve arama onu kullanmaya devam eder; ilk gönderinin
    takip numarası oraya da kopyalanır.
    """
    __tablename__ = "order_shipments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    takip_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kargo_firma: Mapped[str | None] = mapped_column(String(100), nullable=True)
    takip_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # [{line_item_id, quantity, title}] — hangi kalemden kaç adet gitti
    items: Mapped[list] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order] = relationship(back_populates="shipments")


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
    # Couple + kişiye özel: 2. kılıfın tasarımı (1. = assigned_design_id)
    assigned_design_id_2: Mapped[uuid.UUID | None] = mapped_column(
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
    # Çift kılıf: her yarı ayrı üretilir, ayrı "hazır" işaretlenir.
    # is_hazir -> 1. kılıf, is_hazir_2 -> 2. kılıf. Tekil üründe is_hazir_2 kullanılmaz.
    is_hazir_2: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    is_kaliba_eklendi: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    device_model_override: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_model_override_2: Mapped[str | None] = mapped_column(String(100), nullable=True)  # couple 2. kılıf modeli
    kilif_varyasyon: Mapped[str | None] = mapped_column(String(20), nullable=True)  # kişiye özel kılıf rengi/varyasyon
    kilif_varyasyon_2: Mapped[str | None] = mapped_column(String(20), nullable=True)  # couple 2. kılıf varyasyonu
    product_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # shopify_urun_gorseli

    order: Mapped[Order] = relationship(back_populates="line_items")
    assigned_design: Mapped[Design | None] = relationship("Design", foreign_keys=[assigned_design_id])
    assigned_design_2: Mapped[Design | None] = relationship("Design", foreign_keys=[assigned_design_id_2])


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


class ActivityLog(Base):
    """Mağaza aktivite günlüğü — "kim, ne zaman, neyi değiştirdi".

    Sipariş aşamaları OrderStatusHistory'de tutulur; burası KATALOG/AYAR
    tarafı içindir: ürün fiyatı değişti, kupon silindi, tema yayınlandı,
    para iadesi yapıldı… Yazma yolları services/activity.py üzerinden
    kaydeder ve hata asla çağıran işlemi bozmaz.
    """
    __tablename__ = "activity_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=True, index=True
    )

    user_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[str] = mapped_column(String(40), index=True)   # urun_guncelle, kupon_sil…
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)  # urun, kupon…
    entity_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Serbest ayrıntı: {"alan": ["eski", "yeni"]} gibi — panelde satır altında
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


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
    # Tıklanınca gidilecek panel yolu (ör "/kisiye-ozel?store=..&order=.." | "/destek?thread=..")
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
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
    # Slot pozisyonlarini KILITLE: slot silinince kalanlar kaymaz, herkes yerinde kalir.
    # Yarim basilmis bir kaliptan tek kalemi yeniden basarken kritik — kalem 1. slota
    # kayarsa baski birkac mm oynayabiliyor ve ince tasarimlarda bu goze batiyor.
    slot_kilitli: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    print_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    print_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    print_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tamamlandi_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # stage 5'e gecis zamani (arsiv hesabi)

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
    # Geri alinabilir eylemler icin onarim verisi (slot cikarma -> silinen MoldItem
    # alanlari + kalemin onceki bayraklari). {"item": {...}, "li_before": {...},
    # "action": "replan|cancel", "undone": bool}
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
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

    # Mockup: gerçek ürün fotoğrafı şablonu + tasarım alanı dikdörtgeni (kesirsel 0..1)
    mockup_template_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mockup_rect: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {x,y,w,h}
    # Varyasyon başına gerçek foto şablonu: {"<VAR>": {"template_url": str, "rect": {...}}}
    # Eşleşme yoksa mockup_template_url/mockup_rect (varsayılan) kullanılır.
    mockup_variants: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

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


class DesignApproval(Base):
    """Müşteri tasarım onayı — kişiye özel siparişlerde baskı öncesi onay.

    Token'lı public sayfa (siparistakip/onay/{token}) ile müşteri tasarımı görür,
    onaylar veya revizyon ister. Sadece bilgi/rozet — baskıyı engellemez.
    Revizyonda operatör yeni görselle yeni bir kayıt (version+1) oluşturur.
    """
    __tablename__ = "design_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # bekliyor = müşteri henüz karar vermedi | onaylandi | revizyon (müşteri değişiklik istedi)
    status: Mapped[str] = mapped_column(
        String(20), default="bekliyor", server_default=text("'bekliyor'"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    # [{ "image_url": str, "title": str }] — müşteriye gösterilecek tasarımlar
    items: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)            # operatör notu (müşteriye gösterilir)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)   # müşterinin revizyon notu
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="approvals")


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
    balance_usd: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    # Bayinin sabit para birimi (siparis bu para biriminde islenir): TRY | USD
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default=text("'TRY'"))
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
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default=text("'TRY'"))
    kind: Mapped[str] = mapped_column(String(20))  # 'siparis' | 'odeme' | 'duzeltme'
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ref_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    balance_after: Mapped[float] = mapped_column(Numeric(12, 2))
    # Ödemenin dekontu (banka dekontu/makbuz) — PDF ya da görsel. Geriye dönük güvenli takip.
    dekont_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dealer: Mapped["Dealer"] = relationship(back_populates="transactions")


class InstagramDM(Base):
    """Instagram DM otomasyon kaydı — gelen mesaj + botun verdiği yanıt (denetim/panel)."""
    __tablename__ = "instagram_dms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sender_id: Mapped[str] = mapped_column(String(64), index=True)   # IG kullanıcı id (PSID)
    incoming: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)  # order_status/model_ok/faq/fallback
    sent_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class WebAuthnCredential(Base):
    """Kullanıcının geçiş anahtarı (passkey / WebAuthn). Parolasız giriş için."""
    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    credential_id: Mapped[str] = mapped_column(String(400), unique=True, index=True)  # base64url
    public_key: Mapped[str] = mapped_column(Text)      # base64url COSE public key
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0)
    transports: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginAttempt(Base):
    """Başarısız giriş denemesi kaydı — "kim, hangi hesabı, nereden, neyle deniyor".

    Tenant'a bağlı DEĞİL: deneme çoğu zaman var olmayan bir hesaba yapılır.
    Yalnızca BAŞARISIZ denemeler yazılır (başarılı giriş users.last_login_at'te).
    """
    __tablename__ = "login_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # sifre_hatali | hesap_yok | engellendi (rate limit) | passkey_zorunlu
    reason: Mapped[str] = mapped_column(String(30), index=True)
    # Deneme var olan bir hesabaysa o hesap (yoksa NULL) — hedef kim, görünsün.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Note(Base):
    """Siparis notlari (Apple Notes tarzi). Her magaza/bayii + tip (acik/gonderilmis) bir not.
    auto_content: siparislerden otomatik uretilir. manual_content: kullanici elle ekler (korunur).
    serbest notlar: store_id=None, is_serbest=True."""
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    # store_id None ise serbest (elle) not
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=True, index=True
    )
    dealer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # 'acik' | 'gonderilmis' | 'serbest'
    note_type: Mapped[str] = mapped_column(String(20), default="acik", index=True)
    baslik: Mapped[str] = mapped_column(String(200))
    # Otomatik uretilen icerik (siparislerden) — JSON satir listesi
    auto_content: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    # Kullanicinin elle ekledigi serbest metin (korunur, otomatik ureten ezmez)
    manual_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Satir-tabanli checklist icerigi: [{key,text,checked,kind,line_item_id,order_id,uyari}]
    lines: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    is_serbest: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MarketingSubscriber(Base):
    """Pazarlama (kampanya/bilgilendirme) e-posta abonesi — KVKK uyumlu.

    status: pending (onay bekliyor) | subscribed (onaylı) | unsubscribed | bounced.
    Rıza kanıtı consent_at/ip/text alanlarında saklanır (KVKK açık rıza).
    """
    __tablename__ = "marketing_subscribers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_mkt_sub_tenant_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    email: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'"), nullable=False, index=True
    )
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # KVKK açık rıza kanıtı
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_ip: Mapped[str | None] = mapped_column(String(60), nullable=True)
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Çift opt-in onay + kalıcı abonelikten-çıkma token'ı
    confirm_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unsubscribe_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MarketingCampaign(Base):
    """Pazarlama kampanyası — abonelere toplu gönderilen markalı e-posta.

    status: draft (taslak) | sending (gönderiliyor) | sent (tamamlandı) | failed.
    Gövde düz metin (satır sonları paragrafa çevrilir) + opsiyonel CTA butonu.
    """
    __tablename__ = "marketing_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    subject: Mapped[str] = mapped_column(String(300))
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    button_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    button_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Zenginleştirme: üst görsel + önizleme (preheader) metni + isimle kişiselleştirme
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preheader: Mapped[str | None] = mapped_column(String(200), nullable=True)
    personalize: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # Ürün kartları ızgarası: [{"image": "/storage/..", "title": "..", "url": ".."}]
    products: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))

    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default=text("'draft'"), nullable=False, index=True
    )
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    sent_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    fail_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Benzersiz açan / tıklayan abone sayısı (tracking pixel + yönlendirme linki)
    open_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    click_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketingSend(Base):
    """Kampanya × abone gönderim kaydı — açılma/tıklama takibi (id = tracking token)."""
    __tablename__ = "marketing_sends"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True
    )
    subscriber_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_subscribers.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="sent", server_default=text("'sent'"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())



# ═════════════════════════════════════════════════════════════════════
# VİTRİN (STOREFRONT) — kendi e-ticaret kanalımız
# ═════════════════════════════════════════════════════════════════════

class CatalogProduct(Base):
    """Vitrin ürünü — kendi mağazamızın (platform='storefront') satış listesi.

    Design/StockItem üretim varlıklarıdır; bu tablo müşteriye görünen
    listelemedir (fiyat, slug, SEO, görseller). status: draft | active | archived.
    """
    __tablename__ = "catalog_products"
    __table_args__ = (
        UniqueConstraint("store_id", "slug", name="uq_catalog_product_store_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    slug: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    # Düz metin/markdown saklanır, vitrin güvenli render eder (HTML enjeksiyonu yok).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default=text("'draft'"), nullable=False, index=True
    )
    # Zamanlanmış yayın: draft üründe doluysa scheduler saati gelince yayınlar
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Hazır varyant seti — bağlıysa varyantlar setten senkronlanır
    variant_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("variant_sets.id", ondelete="SET NULL"), nullable=True
    )
    # Kişiye özel alanlar: [{key, label, type: text|image|color, required, options}]
    custom_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Sepette 'bunu da ekleyin' önerileri — panelden elle seçilen ürün slug'ları
    cross_sell_slugs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Ürün başına seçilecek model sayısı (couple kılıflar = 2)
    models_per_item: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1")
    )
    # Ürün videosu: YouTube linki veya mp4 URL'i (galeriye eklenir)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(400), nullable=True)

    base_price: Mapped[float] = mapped_column(Numeric(12, 2))
    compare_at_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Tasarım stüdyosu modülleri: bu üründe müşteri hangi kılıf şablonlarıyla
    # kendi tasarımını yapabilir (CaseTemplate.key listesi). Boşsa ürün
    # stüdyoya bağlı değildir.
    # Ürüne bağlanan HAZIR TASARIM MODÜLLERİ (DesignOverlay id listesi).
    # Spotify arayüzü gibi ürüne özel modüller yalnız burada seçildiği üründe
    # çıkar — her üründe görünen genel şablonlarla karışmaz.
    studio_overlays: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"))
    studio_templates: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"))
    # Birim maliyet (KDV hariç alış/üretim) — kâr marjı raporunda kullanılır.
    # Boşsa mağaza ayarındaki varsayılan birim maliyete düşülür.
    cost_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default=text("'TRY'"))

    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    variants: Mapped[list[CatalogVariant]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="CatalogVariant.position"
    )
    images: Mapped[list[CatalogImage]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="CatalogImage.position"
    )
    collections: Mapped[list[CatalogCollection]] = relationship(
        secondary="catalog_product_collections", back_populates="products"
    )


class CatalogVariant(Base):
    """Vitrin varyantı — telefon modeli × kılıf rengi (üretimin düşündüğü boyut).

    model_key = PhoneModel.spec_key (string referans; PhoneModel global/tenant
    katmanlı olduğundan FK değil). variation = StockItem.variation sözlüğü
    (SİYAH/ŞEFFAF...). Fiyat: price_override yoksa ürünün base_price'ı.
    """
    __tablename__ = "catalog_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "model_key", "variation", name="uq_catalog_variant_model_var"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_products.id", ondelete="CASCADE"), index=True
    )

    model_key: Mapped[str] = mapped_column(String(60))
    model_display: Mapped[str] = mapped_column(String(120))
    # Marka (Apple/Samsung/...) — vitrinde iki kademeli seçim (marka → model).
    # PhoneModel.brand'den doldurulur; null → "Diğer" grubunda gösterilir.
    brand: Mapped[str | None] = mapped_column(String(40), nullable=True)
    variation: Mapped[str | None] = mapped_column(String(30), nullable=True)

    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price_override: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    track_stock: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # Opsiyonel: fiziksel boş kılıf stoğuna bağ — satışta StockMovement yazılır.
    stock_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_items.id", ondelete="SET NULL"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[CatalogProduct] = relationship(back_populates="variants")


class CatalogImage(Base):
    """Vitrin ürün görseli — /storage altından SafeStaticFiles ile servis edilir."""
    __tablename__ = "catalog_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_products.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_variants.id", ondelete="SET NULL"), nullable=True
    )

    file_path: Mapped[str] = mapped_column(String(500))
    alt: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[CatalogProduct] = relationship(back_populates="images")


class CheckoutSession(Base):
    """Ödeme oturumu — denetim izi + terk edilmiş sepet kaydı.

    Order YALNIZCA doğrulanmış ödeme callback'inde oluşturulur (hayalet sipariş
    olmaz). status: pending | paid | failed | expired | cancelled.
    token: sağlayıcı conversationId'si; lookup_token: müşteri sipariş takibi.
    customer JSONB'si PII içerir — KVKK: başarısız/expired kayıtlardan 90 gün
    sonra temizlenir (sweeper).
    """
    __tablename__ = "checkout_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    lookup_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20))
    provider_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    shipping_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default=text("'TRY'"))

    # Sunucu fiyatlarıyla doğrulanmış sepet: [{variant_id, title, variant_title,
    # model_key, model_display, variation, sku, quantity, unit_price}]
    cart_snapshot: Mapped[list] = mapped_column(JSONB, default=list)
    # PII: {first_name, last_name, email, phone, address1, city, province, zip, note}
    customer: Mapped[dict] = mapped_column(JSONB, default=dict)
    kvkk_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    callback_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # İndirim kuponu (uygulandıysa) — kod metni denetim/gösterim için kopyalanır
    discount_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    discount_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0, server_default=text("0")
    )
    discount_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discount_codes.id", ondelete="SET NULL"), nullable=True
    )
    # Birden fazla indirim uygulandıysa dökümü — [{id, code, kind, amount,
    # free_shipping, automatic, label}]. Tekil indirimde de doldurulur;
    # kullanım sayacı ödemede buradaki TÜM kuponlar için artar.
    discount_breakdown: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Ödeme akışında ulaşılan son aşama — "nerede vazgeçti" analizi
    # (form_started | form_completed | provider_redirect | provider_returned)
    last_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_stage_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Terk edilmiş sepet hatırlatması — session başına EN FAZLA 1 e-posta
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StorefrontPresence(Base):
    """Vitrin canlı görünüm ping'i — ziyaretçi oturumu başına tek satır.

    Vitrin istemcisi ~20 sn'de bir path + sepet adedini POST'lar; panel
    "Canlı Görünüm" kartı bu tablodan anlık ziyaretçi/sepet sayar. Kişisel
    veri tutulmaz (yalnızca rastgele oturum anahtarı)."""
    __tablename__ = "storefront_presence"
    __table_args__ = (
        UniqueConstraint("store_id", "session_key", name="uq_presence_store_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    session_key: Mapped[str] = mapped_column(String(64))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cart_items: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Ulaşılan EN İLERİ huni aşaması (geri gitmez) — "nerede vazgeçti" analizi
    stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stage_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiscountCode(Base):
    """Vitrin indirim kuponu. kind: percent (%1-100) | amount (TL) | free_shipping.

    usage_count YALNIZCA ödemesi doğrulanmış siparişte artar (terk edilen
    checkout limit yakmaz). once_per_customer: aynı e-posta paid session'da
    kodu bir kez kullanabilir.
    """
    __tablename__ = "discount_codes"
    __table_args__ = (
        UniqueConstraint("store_id", "code", name="uq_discount_store_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    code: Mapped[str] = mapped_column(String(40))  # UPPERCASE saklanır
    kind: Mapped[str] = mapped_column(String(20))  # percent | amount | free_shipping | bxgy
    value: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    # bxgy (X Al Y Öde): buy_x adet alana pay_y adet ücreti — en ucuzlar bedava
    buy_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pay_y: Mapped[int | None] = mapped_column(Integer, nullable=True)

    min_subtotal: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # "N adet üzeri"
    # Yalnızca bu koleksiyondaki ürünlere uygulanır (null = tüm sepet)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_collections.id", ondelete="SET NULL"),
        nullable=True,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    once_per_customer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    # Otomatik: kod girmeden koşulu sağlayan sepete kendiliğinden uygulanır
    # (kod girilirse kod kazanır; otomatikler birleşmez, en kazançlısı seçilir)
    is_automatic: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    # Birleşebilir: sepet indirimi (%/TL/XalYöde) ile kargo indirimi AYNI
    # anda uygulanabilir — yalnız iki tarafın da bu bayrağı açıksa
    # (Shopify "Combinations"). Kapalıysa tek indirim kazanır.
    combinable: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    # Vitrinde (sepet/duyuru) gösterilecek özel kampanya mesajı — boşsa
    # kural bilgilerinden otomatik üretilir ("3 Al 2 Öde — sepette otomatik…")
    promo_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Customer(Base):
    """Müşteri CRM kaydı — siparişlerden türetilen birleşik görünüm.

    E-posta bazlı tekilleştirme (tenant içinde). Agregalar (orders_count,
    total_spent...) her sipariş upsert'inde YENİDEN hesaplanır (idempotent —
    tekrarlanan sync'ler şişirmez). KVKK: veri zaten sözleşme ifası kapsamında
    sipariş kayıtlarında mevcut; bu tablo yalnızca birleşik görünümdür.
    """
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_customer_tenant_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    email: Mapped[str] = mapped_column(String(200))  # lowercase saklanır
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    orders_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_spent: Mapped[float] = mapped_column(
        Numeric(14, 2), default=0, server_default=text("0")
    )
    first_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Bülten aboneliği (KVKK: açık rıza — opt-in zamanı saklanır)
    # Hoş geldin e-postası (bülten kaydı) — müşteri başına TEK sefer
    welcome_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepts_marketing: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    marketing_opted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Vitrin müşteri hesabı (şifresiz giriş): kayıtlı adres + tek kullanımlık kod
    default_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Adres defteri (Shopify address book) — ilk kayıt varsayılandır
    addresses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Hesaba bağlı favoriler: ürün slug listesi (cihazlar arası senkron)
    favorites: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    login_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    login_code_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_code_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VariantSet(Base):
    """Hazır varyant seti — model listesi TEK yerden yönetilir; sete bağlı
    ürünlerin varyantları set kaydedilince senkronlanır (stok/adet korunur).

    items: [{model_key, model_display, brand, variation, price_override}]
    """
    __tablename__ = "variant_sets"
    __table_args__ = (
        UniqueConstraint("store_id", "name", name="uq_variant_set_store_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(120))
    items: Mapped[list] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BlogPost(Base):
    """Vitrin blog yazısı (Shopify Online Store > Blog) — SEO içeriği."""
    __tablename__ = "blog_posts"
    __table_args__ = (
        UniqueConstraint("store_id", "slug", name="uq_blog_store_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    slug: Mapped[str] = mapped_column(String(220))
    title: Mapped[str] = mapped_column(String(300))
    excerpt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DesignRequest(Base):
    """Müşterinin kendi tasarım talebi — görsel yükler, açıklama yazar;
    mağaza panelinden incelenir (müşteriyle bağ kurma kanalı)."""
    __tablename__ = "design_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    customer_email: Mapped[str] = mapped_column(String(200))  # lowercase
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(  # acik | incelendi | teklif | tamam | red
        String(20), default="acik", server_default=text("'acik'")
    )
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StockAlert(Base):
    """'Gelince haber ver' kaydı — stoksuz varyanta e-posta bırakılır,
    stok girilince bir kez bildirim gider (notified_at kilidi)."""
    __tablename__ = "stock_alerts"
    __table_args__ = (
        UniqueConstraint("variant_id", "email", name="uq_stock_alert_variant_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_variants.id", ondelete="CASCADE"), index=True
    )

    email: Mapped[str] = mapped_column(String(200))  # lowercase saklanır
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Refund(Base):
    """Panelden yapılan para iadesi kaydı (vitrin siparişleri).

    Başarılı/başarısız TÜM denemeler kaydedilir (denetim izi). Tutar doğrulaması
    (ödenen − önceki başarılı iadeler) endpoint'te yapılır.
    """
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    checkout_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checkout_sessions.id", ondelete="SET NULL"), nullable=True
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20))  # succeeded | failed
    provider: Mapped[str] = mapped_column(String(20))
    provider_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


catalog_product_collections = Table(
    "catalog_product_collections",
    Base.metadata,
    Column("product_id", UUID(as_uuid=True),
           ForeignKey("catalog_products.id", ondelete="CASCADE"), primary_key=True),
    Column("collection_id", UUID(as_uuid=True),
           ForeignKey("catalog_collections.id", ondelete="CASCADE"), primary_key=True),
)


class CatalogCollection(Base):
    """Vitrin koleksiyonu — ürün grubu (örn 'Retro', 'Minimal').

    Ürünlerle M2M; vitrinde koleksiyon sayfası + filtre çipleri olarak görünür.
    """
    __tablename__ = "catalog_collections"
    __table_args__ = (
        UniqueConstraint("store_id", "slug", name="uq_catalog_collection_store_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    slug: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    # Akıllı koleksiyon: ürünler elle değil KURALLA seçilir. Üyelik yine aynı
    # M2M tablosunda maddileşir (services/smart_collections.py) — vitrin,
    # filtreler, kuponlar ve feed hiç değişmeden çalışır.
    is_smart: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    rules_match: Mapped[str] = mapped_column(
        String(4), default="all", server_default=text("'all'")
    )  # all = tüm kurallar, any = herhangi biri

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    products: Mapped[list[CatalogProduct]] = relationship(
        secondary=catalog_product_collections, back_populates="collections"
    )


class PushSubscription(Base):
    """Web Push aboneliği (PWA mobil bildirim). Her cihaz/tarayıcı için bir kayıt.

    Panel kullanıcısı bildirimleri açtığında tarayıcı bir PushSubscription üretir
    (endpoint + p256dh + auth). Backend bunları saklar ve pywebpush ile VAPID
    imzalı bildirim gönderir. is_platform_admin kullanıcıların abonelikleri
    cross-tenant olaylarda (yeni mağaza onayı) da kullanılır.
    """
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductReview(Base):
    """Ürün yorumu — YALNIZCA doğrulanmış alıcı (lookup_token'lı paid session).

    status: pending (panelde onay bekler) | approved | rejected.
    Sipariş başına ürün başına 1 yorum (unique kısıt).
    """
    __tablename__ = "product_reviews"
    __table_args__ = (
        UniqueConstraint("product_id", "checkout_session_id",
                         name="uq_review_product_session"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_products.id", ondelete="CASCADE"), index=True
    )
    checkout_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checkout_sessions.id", ondelete="SET NULL"), nullable=True
    )

    author_name: Mapped[str] = mapped_column(String(60))
    # review = yıldızlı yorum (satın alma şartlı) | question = ürün sorusu
    kind: Mapped[str] = mapped_column(
        String(20), default="review", server_default=text("'review'")
    )
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 1-5 (soruda yok)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Soru-cevap: mağazanın yanıtı (yalnız yanıtlanmış sorular vitrinde görünür)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InstagramPost(Base):
    """Instagram içerik taslağı — planlama + AI üretim + onay kuyruğu.

    Her taslak bir MAĞAZAYA (marka/profil) aittir; mağazanın kendi IG hesabından
    (store.config['instagram']['handle']) paylaşılır. Akış: taslak -> onaylandi
    -> paylasildi (ya da red). status'e göre kuyrukta gösterilir.
    Öğrenme: onay/düzenleme feedback'i sonraki üretimlere few-shot beslenir.
    """
    __tablename__ = "instagram_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    kind: Mapped[str] = mapped_column(String(10), default="post")     # post | story
    style: Mapped[str] = mapped_column(String(10), default="mockup")  # mockup | ugc
    status: Mapped[str] = mapped_column(
        String(12), default="taslak", server_default=text("'taslak'"), index=True
    )  # taslak | onaylandi | paylasildi | red

    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    design_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("designs.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Öğrenme sinyali: {"orijinal_caption": ..., "duzenlenmis": ..., "begeni": true/false}
    feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═════════════════════════════════════════════════════════════════════
# TASARIM STÜDYOSU (müşteri) — kılıfını kendi tasarlar
# ═════════════════════════════════════════════════════════════════════

class CaseTemplate(Base):
    """Boş kılıf şablonu — müşterinin üzerine tasarım yaptığı zemin.

    Görseli (mockup) panelden yüklenir. BASKI ALANI şablonun kendi
    piksellerine göre ORANSAL tanımlanır (0-1); böylece editör hangi
    çözünürlükte gösterirse göstersin, baskıya giden dosya aynı fiziksel
    alana denk gelir. print_width_mm/print_height_mm gerçek baskı ölçüsüdür —
    baskıya hazır dosya bu ölçü ve DPI'dan üretilir.
    """
    __tablename__ = "case_templates"
    __table_args__ = (
        UniqueConstraint("store_id", "key", name="uq_case_template_store_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    key: Mapped[str] = mapped_column(String(40))          # seffaf | beyaz | siyah | parlak | magsafe
    label: Mapped[str] = mapped_column(String(120))       # müşteriye görünen ad
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # mockup

    # Baskı alanı — şablon görseline göre oran (0-1)
    area_x: Mapped[float] = mapped_column(Numeric(6, 4), default=0.1)
    area_y: Mapped[float] = mapped_column(Numeric(6, 4), default=0.1)
    area_w: Mapped[float] = mapped_column(Numeric(6, 4), default=0.8)
    area_h: Mapped[float] = mapped_column(Numeric(6, 4), default=0.8)
    # Baskı alanının köşe yuvarlaklığı (kısa kenara oran, 0-0.5)
    area_radius: Mapped[float] = mapped_column(Numeric(6, 4), default=0.08)
    # Basılamayan bölgeler: kamera adası, MagSafe halkası, kenar payı…
    # [{x, y, w, h, radius, label}] — hepsi şablona ORANSAL (0-1)
    cutouts: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    # Gerçek baskı ölçüsü (mm) + hedef çözünürlük — baskı dosyası bundan üretilir
    print_width_mm: Mapped[int] = mapped_column(Integer, default=70)
    print_height_mm: Mapped[int] = mapped_column(Integer, default=145)
    print_dpi: Mapped[int] = mapped_column(Integer, default=300)

    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DesignOverlay(Base):
    """Hazır tasarım şablonu — müşterinin tasarımının ÜSTÜNE binen şeffaf PNG.

    Örnek: fotoğraf çerçevesi. Müşteri görsel yükler, görsel ALTTA kalır,
    çerçeve üstüne oturur; yazılar ise çerçevenin de üstündedir. Bu sıralama
    editörde, önizlemede ve baskı dosyasında aynıdır (bkz. design_render).

    Görsel baskı ALANINI tam kaplar (taşınmaz/ölçeklenmez) — çerçeve kılıfa
    bire bir otursun diye. Hangi kılıf tipine ait olduğu case_template_id ile
    belirlenir; null ise o mağazanın tüm kılıflarında görünür.
    """
    __tablename__ = "design_overlays"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    case_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_templates.id", ondelete="CASCADE"),
        nullable=True, index=True
    )

    label: Mapped[str] = mapped_column(String(120))
    image_path: Mapped[str] = mapped_column(String(500))
    # Küçük önizleme (liste kartı) — yoksa image_path kullanılır
    thumb_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # "serbest": müşteri şablonu bir katman gibi kullanır, kendi görsel/yazısını
    #   ekler, taşır (varsayılan davranış).
    # "kisitli": şablon SABİTTİR; müşteri yalnızca aşağıda tanımlı alanları
    #   doldurur (ör. forma numarası + isim) ve açılabilir öğeleri açıp kapatır.
    #   Serbest görsel/yazı ekleyemez, hiçbir şeyi taşıyamaz.
    mod: Mapped[str] = mapped_column(String(10), default="serbest",
                                     server_default=text("'serbest'"))
    # True → bu modül YALNIZ atandığı ürünlerde görünür (ürün detayında
    # seçilir). False → her ürünün stüdyosunda genel şablon olarak çıkar.
    sadece_urunde: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"))
    # Şablon teması/modülü — vitrinde şablonlar buna göre gruplanır
    # ("Forma", "Spotify", "Fotoğraf çerçevesi"…). Boşsa "Diğer".
    kategori: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Kısıtlı moddaki alan tanımları — hepsi şablona ORANSAL (0-1):
    # yazı    : {key, tip:"yazi", etiket, varsayilan, max, x, y, w, size, font, renk, hiza}
    # görsel  : {key, tip:"gorsel", etiket, image_path, x, y, w, h, varsayilan:true|false}
    #           (panelden yüklenen SABİT öğe — müşteri sadece açıp kapatır)
    # foto    : {key, tip:"foto", etiket, x, y, w, h, sigdir:"kapla"|"sigdir"}
    #           (MÜŞTERİNİN yüklediği görsel; çerçeveye otomatik yerleşir)
    # ilerleme: {key, tip:"ilerleme", etiket, x, y, w, kalinlik, boyut, renk, renk_pasif,
    #           kaynak_gecen, kaynak_toplam} — iki süre alanından oran hesaplanır,
    #           Spotify tarzı ilerleme çubuğu + noktası çizilir
    # Her alanda "arkada": true ise şablonun ALTINA çizilir (şablon delikliyse
    # fotoğraf oradan görünür), yoksa üstüne.
    alanlar: Mapped[list] = mapped_column(JSONB, default=list,
                                          server_default=text("'[]'::jsonb"))

    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DesignAsset(Base):
    """Müşterinin stüdyoya yüklediği görsel.

    ORİJİNAL dosya olduğu gibi saklanır (küçültülmez, yeniden sıkıştırılmaz) —
    baskıya giden dosya bundan üretilecek. Ayrıca hafif bir web önizlemesi
    tutulur; tarayıcı 40 MP'lik fotoğrafı tuvalde taşımak zorunda kalmasın.
    """
    __tablename__ = "design_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    original_path: Mapped[str] = mapped_column(String(500))
    preview_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomerDesign(Base):
    """Müşterinin kaydettiği kılıf tasarımı — hesabına bağlı, kaldığı yerden devam.

    layers: tuval içeriği [{type:'image'|'text', ...}] — konum/ölçek/dönüş
    BASKI ALANINA göre oransal (0-1) tutulur; ekran boyutundan bağımsızdır,
    böylece aynı tasarım hem önizlemede hem baskı dosyasında aynı yere düşer.

    status: draft (düzenleniyor) | ready (sipariş için hazır) | ordered (sipariş edildi)
    """
    __tablename__ = "customer_designs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(120), default="Tasarımım")
    template_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Seçilen telefon modeli (varyant) — sipariş anında da doğrulanır
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_variants.id", ondelete="SET NULL"), nullable=True
    )
    layers: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    # Tuvalde gösterilen küçük önizleme (müşteri listesi + panel için)
    preview_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Baskıya hazır çıktı (sipariş sonrası sunucuda üretilir)
    print_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Vektörel + CMYK baskı dosyası (matbaa/RIP için); PNG'nin yanında durur
    print_pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Rötuş/CMYK sonrası hazırlanan NUMUNE — müşteri onayında bu gösterilir
    # (yoksa stüdyo önizlemesine düşülür)
    proof_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(
        String(12), default="draft", server_default=text("'draft'"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IntegrationKey(Base):
    """Dış entegrasyona (e-fatura entegratörü, muhasebe yazılımı…) verilen
    okuma anahtarı.

    Anahtarın kendisi SAKLANMAZ — yalnız SHA-256 özeti tutulur; panelde bir
    kez gösterilir. Böylece veritabanı sızsa bile anahtar geri üretilemez.
    Yetki mağaza bazlıdır: anahtar yalnız kendi mağazasının siparişlerini
    görür ve yalnız fatura bilgisi yazabilir.
    """
    __tablename__ = "integration_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    # Kimin kullandığı belli olsun: "Birfatura", "Muhasebeci" …
    label: Mapped[str] = mapped_column(String(80))
    # Panelde listelerken gösterilen baş harfler (bfk_ab12…)
    key_prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
