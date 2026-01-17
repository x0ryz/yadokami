from typing import AsyncGenerator

from cryptography.fernet import Fernet
from sqlalchemy import MetaData, String, TypeDecorator
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from src.core.config import settings

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


try:
    cipher_suite = Fernet(settings.DB_ENCRYPTION_KEY)
except Exception:
    print("WARNING: DB_ENCRYPTION_KEY is missing or invalid. Encryption will fail.")
    cipher_suite = None  # type: ignore


class EncryptedString(TypeDecorator):
    """Шифрує дані перед записом у БД і дешифрує при отриманні."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Шифруємо дані перед записом у базу."""
        if value is not None and cipher_suite:
            if isinstance(value, str):
                value = value.encode("utf-8")
            encrypted = cipher_suite.encrypt(value)
            return encrypted.decode("utf-8")
        return value

    def process_result_value(self, value, dialect):
        """Дешифруємо дані після отримання з бази."""
        if value is not None and cipher_suite:
            try:
                decrypted = cipher_suite.decrypt(value.encode("utf-8"))
                return decrypted.decode("utf-8")
            except Exception:
                return None
        return value


class Base(AsyncAttrs, DeclarativeBase):
    metadata = metadata


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
