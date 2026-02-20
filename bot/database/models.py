from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gender: Mapped[str] = mapped_column(String(16))
    age: Mapped[int] = mapped_column(Integer)
    height_cm: Mapped[float] = mapped_column(Float)
    weight_start_kg: Mapped[float] = mapped_column(Float)
    activity_level: Mapped[str] = mapped_column(String(32))
    goal: Mapped[str] = mapped_column(String(16))
    target_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    weight_plan_mode: Mapped[str | None] = mapped_column(String(16), nullable=True, default=None)
    weight_plan_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    weight_plan_start_kg: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    daily_water_target_ml: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    meal_reminder_times: Mapped[str | None] = mapped_column(String(64), nullable=True, default="9,13,19")
    daily_calories_target: Mapped[float] = mapped_column(Float)
    daily_protein_target: Mapped[float] = mapped_column(Float)
    daily_fat_target: Mapped[float] = mapped_column(Float)
    daily_carbs_target: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    weight_logs: Mapped[list["WeightLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    meal_logs: Mapped[list["MealLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    water_logs: Mapped[list["WaterLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    meal_templates: Mapped[list["MealTemplate"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    conversation_messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    daily_checkins: Mapped[list["DailyCheckin"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    achievements: Mapped[list["Achievement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WeightLog(Base):
    __tablename__ = "weight_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    weight_kg: Mapped[float] = mapped_column(Float)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="weight_logs")


class MealLog(Base):
    __tablename__ = "meal_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(Text)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    photo_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meal_type: Mapped[str] = mapped_column(String(32), default="snack")
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="meal_logs")


class WaterLog(Base):
    __tablename__ = "water_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    amount_ml: Mapped[int] = mapped_column(Integer)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="water_logs")


class MealTemplate(Base):
    __tablename__ = "meal_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    meal_type: Mapped[str] = mapped_column(String(32), default="snack")
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="meal_templates")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="conversation_messages")


class DailyCheckin(Base):
    __tablename__ = "daily_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    checkin_date: Mapped[date] = mapped_column(Date, index=True)
    calories_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    protein_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    logged_meals: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="daily_checkins")


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    badge_key: Mapped[str] = mapped_column(String(64))
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="achievements")


class GroupChat(Base):
    __tablename__ = "group_chats"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GroupChatMember(Base):
    __tablename__ = "group_chat_members"

    chat_id: Mapped[int] = mapped_column(
        ForeignKey("group_chats.chat_id", ondelete="CASCADE"),
        primary_key=True,
    )
    telegram_id: Mapped[int] = mapped_column(primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

