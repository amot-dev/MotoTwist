from alembic import command
from alembic.config import Config
from socket import socket
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from time import sleep

from config import logger
from settings import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def apply_migrations():
    logger.info("Applying database migrations...")
    alembic_cfg = Config("alembic.ini")
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