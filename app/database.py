from alembic import command
from alembic.config import Config
from os import getenv
from socket import socket
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from time import sleep

DB_HOST = getenv("POSTGRES_HOST", "db")
DB_PORT = getenv("POSTGRES_PORT", "5432")
DB_NAME = getenv("POSTGRES_DB", "mototwist")
DB_USER = getenv("POSTGRES_USER", "mototwist")
DB_PASSWORD = getenv("POSTGRES_PASSWORD", "password")

SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def apply_migrations():
    from config import logger
    logger.info("Applying database migrations...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

def wait_for_db():
    from config import logger
    while True:
        s = socket()
        s.settimeout(2)
        if s.connect_ex((DB_HOST, int(DB_PORT))) == 0:
            logger.info("Database is up at %s:%s", DB_HOST, DB_PORT)
            s.close()
            break
        logger.info("Database unavailable at %s:%s. Sleeping 1s", DB_HOST, DB_PORT)
        sleep(1)