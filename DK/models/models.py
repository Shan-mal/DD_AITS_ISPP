from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, Enum, Index, CheckConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class SessionStatus(str, PyEnum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"

class TransactionStatus(str, PyEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"

class SpotStatus(str, PyEnum):
    free = "free"
    occupied = "occupied"
    reserved = "reserved"
    maintenance = "maintenance"

class UserRole(str, PyEnum):
    client = "client"
    admin = "admin"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.client, nullable=False)
    benefit_category = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehicles = relationship("Vehicle", back_populates="owner", lazy="dynamic")
    payment_methods = relationship("PaymentMethod", back_populates="user", lazy="dynamic")
    transactions = relationship("Transaction", back_populates="user", lazy="dynamic")
    audit_logs = relationship("AuditLog", back_populates="user", lazy="dynamic")

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    plate_number = Column(String(20), unique=True, nullable=False, index=True)
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    color = Column(String(50), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="vehicles")
    parking_sessions = relationship("ParkingSession", back_populates="vehicle", lazy="dynamic")

class ParkingSpot(Base):
    __tablename__ = "parking_spots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    section = Column(String(10), nullable=False)
    spot_number = Column(Integer, nullable=False)
    status = Column(Enum(SpotStatus), default=SpotStatus.free, nullable=False)
    sensor_id = Column(String(50), unique=True, nullable=True)
    floor = Column(Integer, nullable=True)
    is_handicapped = Column(Boolean, default=False)
    is_electric = Column(Boolean, default=False)
    hourly_rate_multiplier = Column(Float, default=1.0)

    __table_args__ = (
        Index("ix_parking_spots_section_spot", "section", "spot_number", unique=True),
        CheckConstraint("hourly_rate_multiplier > 0", name="ck_positive_multiplier"),
    )

    sessions = relationship("ParkingSession", back_populates="spot", lazy="dynamic")

class Tariff(Base):
    __tablename__ = "tariffs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price_per_minute = Column(Float, nullable=False)
    max_daily = Column(Float, nullable=True)
    grace_period_minutes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    applicable_role = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("ParkingSession", back_populates="tariff", lazy="dynamic")

class ParkingSession(Base):
    __tablename__ = "parking_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    spot_id = Column(Integer, ForeignKey("parking_spots.id"), nullable=False)
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=False)
    entry_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.active, nullable=False)
    total_cost = Column(Float, nullable=True)
    grace_used = Column(Boolean, default=False)

    vehicle = relationship("Vehicle", back_populates="parking_sessions")
    spot = relationship("ParkingSpot", back_populates="sessions")
    tariff = relationship("Tariff", back_populates="sessions")
    transactions = relationship("Transaction", back_populates="session", lazy="dynamic")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("parking_sessions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="RUB")
    status = Column(Enum(TransactionStatus), default=TransactionStatus.pending, nullable=False)
    external_id = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("ParkingSession", back_populates="transactions")
    user = relationship("User", back_populates="transactions")
    payment_method = relationship("PaymentMethod", back_populates="transactions")

class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), nullable=False)
    last4 = Column(String(4), nullable=True)
    card_type = Column(String(20), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payment_methods")
    transactions = relationship("Transaction", back_populates="payment_method", lazy="dynamic")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")