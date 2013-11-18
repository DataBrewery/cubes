from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, ForeignKey

engine = create_engine('sqlite:///modeller.sqlite', convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    # you will have to import them first before calling init_db()
    Base.metadata.create_all(bind=engine)

class Cube(Base):
    __tablename__ = "cubes"

    id = Column(Integer, primary_key=True)

    name = Column(String)
    label = Column(String)
    description = Column(String)
    info = Column(String)
    category = Column(String)
    key = Column(String)
    store = Column(String)

class Dimension(Base):
    __tablename__ = "dimensions"

    id = Column(Integer, primary_key=True)

    name = Column(String)
    label = Column(String)
    description = Column(String)
    info = Column(String)
    role = Column(String)

    levels = relationship('Level', backref='dimension', lazy='dynamic')

class Level(Base):
    __tablename__ = "levels"

    id = Column(Integer, primary_key=True)

    name = Column(String)
    label = Column(String)
    description = Column(String)
    info = Column(String)

    dimension_id = Column(Integer, ForeignKey('dimensions.id'))

