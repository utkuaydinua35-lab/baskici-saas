"""email_logs teşhis alanları — 'mail ulaştı mı' sorusu cevaplanabilsin

Revision ID: d1a2b3c4e5f6
Revises: c9f1a3d84e27
"""
from alembic import op
import sqlalchemy as sa

revision = "d1a2b3c4e5f6"
down_revision = "c9f1a3d84e27"
branch_labels = None
depends_on = None


def upgrade():
    # Siparişe bağlı OLMAYAN mail de kaydedilebilsin (destek yanıtı, şifre
    # sıfırlama): teşhis için gönderimin kendisi değerli.
    op.alter_column("email_logs", "order_id", existing_type=sa.dialects.postgresql.UUID(),
                    nullable=True)
    op.add_column("email_logs", sa.Column("provider", sa.String(20), nullable=True))
    op.add_column("email_logs",
                  sa.Column("provider_message_id", sa.String(120), nullable=True))
    op.add_column("email_logs", sa.Column("error", sa.Text(), nullable=True))
    op.add_column("email_logs", sa.Column("last_event", sa.String(40), nullable=True))
    op.add_column("email_logs",
                  sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_logs",
                  sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_logs",
                  sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_logs",
                  sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True))
    # Webhook olayları message id ile eşleşiyor — sıcak yol, indeks şart.
    op.create_index("ix_email_logs_provider_message_id", "email_logs",
                    ["provider_message_id"])


def downgrade():
    op.drop_index("ix_email_logs_provider_message_id", table_name="email_logs")
    for c in ("opened_at", "bounced_at", "delivered_at", "last_event_at",
              "last_event", "error", "provider_message_id", "provider"):
        op.drop_column("email_logs", c)
    op.alter_column("email_logs", "order_id", existing_type=sa.dialects.postgresql.UUID(),
                    nullable=False)
