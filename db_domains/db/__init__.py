from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from config import app_config

# Create the database engine
engine: Engine = create_engine(
    app_config.DATABASE_URL, connect_args={'connect_timeout': 10}
)

# Configure session factory
DBSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def create_db(file: str):
    """
    :param str file: file name
    This method is used to create the database tables using create_all method.
    """
    temp_engine = create_engine(file)  # Create a temp engine for initialization
    Base.metadata.create_all(temp_engine)


def init_db():
    """
    Bind the metadata to the engine and configure the session.
    """
    Base.metadata.bind = engine
    DBSession.configure(bind=engine)


# ✅ Dependency function for FastAPI
def get_db():
    """
    Dependency function to provide a database session.
    Ensures session is created and properly closed after use.
    """
    db: Session = DBSession()  # Create a new session
    try:
        yield db  # Provide the session
    finally:
        db.close()  # Close the session after request
