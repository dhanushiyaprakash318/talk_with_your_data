from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_USER = "root"
DB_PASSWORD = "dhanu1837"
DB_HOST = "localhost"
DB_PORT = "3306"
DB_NAME = "salonpos"

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
