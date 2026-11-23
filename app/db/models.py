from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Kolkata", server_default="Asia/Kolkata"
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    accounts: Mapped[list["Account"]] = relationship(back_populates="user")
    sender_stats: Mapped[list["SenderStat"]] = relationship(back_populates="user")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="gmail", server_default="gmail"
    )
    account_email: Mapped[str] = mapped_column(String(320), nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    history_cursor: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )

    user: Mapped[User] = relationship(back_populates="accounts")
    threads: Mapped[list["Thread"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "account_email", name="uq_accounts_user_email"),
        CheckConstraint(
            "status IN ('active', 'needs_reconnect')",
            name="ck_accounts_status",
        ),
    )


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_thread_id: Mapped[str] = mapped_column(String(256), nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False, default="", server_default="")
    last_sender: Mapped[str] = mapped_column(
        String(320), nullable=False, default="", server_default=""
    )
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_from_me: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", server_default="open"
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[Account] = relationship(back_populates="threads")
    classifications: Mapped[list["Classification"]] = relationship(back_populates="thread")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="thread")
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="thread")

    __table_args__ = (
        UniqueConstraint("account_id", "provider_thread_id", name="uq_threads_account_provider"),
        CheckConstraint(
            "status IN ('open', 'answered', 'ignored', 'snoozed', 'done')",
            name="ck_threads_status",
        ),
    )


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    needs_reply: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    urgency: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(String(200), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    thread: Mapped[Thread] = relationship(back_populates="classifications")

    __table_args__ = (
        CheckConstraint("urgency >= 1 AND urgency <= 5", name="ck_classifications_urgency"),
        CheckConstraint(
            "category IN ('lead', 'client', 'investor', 'hiring', 'internal', "
            "'vendor', 'personal', 'other')",
            name="ck_classifications_category",
        ),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default="telegram", server_default="telegram"
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    telegram_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    thread: Mapped[Thread] = relationship(back_populates="alerts")

    __table_args__ = (
        CheckConstraint("channel IN ('telegram')", name="ck_alerts_channel"),
        CheckConstraint("kind IN ('realtime', 'digest')", name="ck_alerts_kind"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    thread: Mapped[Thread] = relationship(back_populates="feedback_items")

    __table_args__ = (
        CheckConstraint(
            "label IN ('not_important', 'mattered', 'done', 'snooze')",
            name="ck_feedback_label",
        ),
    )


class SenderStat(Base):
    __tablename__ = "sender_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    importance_weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    replies_sent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sender_stats")

    __table_args__ = (UniqueConstraint("user_id", "sender", name="uq_sender_stats_user_sender"),)
