from datetime import datetime, date
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class KoboSubmission(Base):
    """One Kobo submission = one outlet visit.

    Production schema stores important Kobo fields in real SQL columns.
    Product/competitor/ring-pull values are stored in normalized child tables.
    The old JSONB payload column is no longer used.
    """
    __tablename__ = "kobo_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    submission_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    report_date: Mapped[date | None] = mapped_column(Date, index=True)

    region: Mapped[str | None] = mapped_column(String(30), index=True)
    dealer: Mapped[str | None] = mapped_column(String(30), index=True)
    group_no: Mapped[int | None] = mapped_column(Integer)
    member_no: Mapped[int | None] = mapped_column(Integer)
    total_outlet_visit_target: Mapped[int | None] = mapped_column(Integer)

    outlet_name: Mapped[str | None] = mapped_column(String(255))
    outlet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    is_new_outlet: Mapped[bool | None] = mapped_column(Boolean)

    submitter_name: Mapped[str | None] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(80))

    location_text: Mapped[str | None] = mapped_column(Text)
    gps_text: Mapped[str | None] = mapped_column(Text)
    gps_latitude: Mapped[float | None] = mapped_column(Float)
    gps_longitude: Mapped[float | None] = mapped_column(Float)

    key_issue_text: Mapped[str | None] = mapped_column(Text)
    suggestion_text: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product_metrics: Mapped[list["KoboProductMetric"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan", lazy="selectin"
    )
    competitor_metrics: Mapped[list["KoboCompetitorMetric"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan", lazy="selectin"
    )
    ring_pull_metrics: Mapped[list["KoboRingPullMetric"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan", lazy="selectin"
    )


class KoboProductMetric(Base):
    __tablename__ = "kobo_product_metrics"
    __table_args__ = (UniqueConstraint("submission_id", "product_name", name="uq_product_metric_submission_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("kobo_submissions.id", ondelete="CASCADE"), index=True)
    product_name: Mapped[str] = mapped_column(String(255), index=True)

    status: Mapped[str | None] = mapped_column(String(80))
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    movement_score: Mapped[int | None] = mapped_column(Integer)
    stock_status: Mapped[str | None] = mapped_column(String(80))
    bbe_date: Mapped[str | None] = mapped_column(String(80))
    buy_in_price: Mapped[float | None] = mapped_column(Float)
    sell_out_price: Mapped[float | None] = mapped_column(Float)
    ring_pull_value: Mapped[float | None] = mapped_column(Float)
    new_outlet_purchase: Mapped[bool] = mapped_column(Boolean, default=False)
    volume_ctn: Mapped[float | None] = mapped_column(Float)

    submission: Mapped["KoboSubmission"] = relationship(back_populates="product_metrics")


class KoboCompetitorMetric(Base):
    __tablename__ = "kobo_competitor_metrics"
    __table_args__ = (UniqueConstraint("submission_id", "product_name", name="uq_competitor_metric_submission_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("kobo_submissions.id", ondelete="CASCADE"), index=True)
    product_name: Mapped[str] = mapped_column(String(255), index=True)

    status: Mapped[str | None] = mapped_column(String(80))
    movement_score: Mapped[int | None] = mapped_column(Integer)
    stock_status: Mapped[str | None] = mapped_column(String(80))
    buy_in_price: Mapped[float | None] = mapped_column(Float)
    sell_out_price: Mapped[float | None] = mapped_column(Float)

    submission: Mapped["KoboSubmission"] = relationship(back_populates="competitor_metrics")


class KoboRingPullMetric(Base):
    __tablename__ = "kobo_ring_pull_metrics"
    __table_args__ = (UniqueConstraint("submission_id", "product_name", name="uq_ring_pull_metric_submission_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("kobo_submissions.id", ondelete="CASCADE"), index=True)
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    qty_ctn: Mapped[int] = mapped_column(Integer, default=0)

    submission: Mapped["KoboSubmission"] = relationship(back_populates="ring_pull_metrics")


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), default="kobo")
    status: Mapped[str] = mapped_column(String(50))
    message: Mapped[str | None] = mapped_column(Text)
    fetched: Mapped[int | None] = mapped_column(Integer)
    synced: Mapped[int | None] = mapped_column(Integer)
    skipped: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
