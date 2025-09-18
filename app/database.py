from alembic import command
from alembic.config import Config
from socket import socket
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from time import sleep

from config import logger
from settings import settings


engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
Base = declarative_base()


async def get_db():
    """
    Dependency to get a database session.
    """
    async with SessionLocal() as session:
        yield session


def apply_migrations():
    logger.info("Applying database migrations...")
    alembic_cfg = Config("alembic.ini")

    # Alembic needs a sync connection
    alembic_cfg.set_main_option('sqlalchemy.url', settings.SQLALCHEMY_DATABASE_URL)
    alembic_cfg.attributes['target_metadata'] = Base.metadata
    command.upgrade(alembic_cfg, "head")


def wait_for_db():
    while True:
        s = socket()
        s.settimeout(2)
        if s.connect_ex((settings.POSTGRES_HOST, settings.POSTGRES_PORT)) == 0:
            logger.info(f"Database is up at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
            s.close()
            break
        logger.info(f"Database unavailable at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}. Sleeping 1s")
        sleep(1)