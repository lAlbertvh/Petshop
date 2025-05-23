from sqlalchemy import create_engine, Column, Integer, String, JSON, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import contextlib # Импортируем contextlib

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)
    cart = Column(JSON, default=list)
    state = Column(String, default="MAIN_MENU")

    def __repr__(self):
        return f"<User(id={self.id}, cart={self.cart}, state='{self.state}')>"

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    category = Column(String)
    subcategory = Column(String)
    price = Column(Integer)
    description = Column(String)
    image_path = Column(String)

# Database setup
db_url = os.getenv("DATABASE_URL")
if db_url:
    engine = create_engine(db_url)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "bot.db")
    engine = create_engine(f"sqlite:///{DB_PATH}")

Base.metadata.create_all(engine)

# Define SessionLocal as a factory for sessions
# autocommit=False ensures you explicitly commit transactions
# autoflush=False prevents flushing before query operations
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to get a database session
@contextlib.contextmanager # ДОБАВЛЕНО: Декоратор для использования функции как контекстного менеджера
def get_session():
    """
    Provides a SQLAlchemy session.
    Use with 'with' statement for proper session management:
    with get_session() as session:
        # ... database operations ...
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()