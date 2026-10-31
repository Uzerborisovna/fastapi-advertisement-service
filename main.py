import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Query
from sqlalchemy import create_engine, Column, Integer, String, Numeric, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime
from pydantic import BaseModel, Field

# 1. Загружаем переменные окружения
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 2. Настройка SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 3. Модель БД (ИСПРАВЛЕНО: created_at теперь полноценная дата)
class Advertisement(Base):
    __tablename__ = "advertisements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    author = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Создаем таблицы
Base.metadata.create_all(bind=engine)


# 4. Схемы Pydantic (ИСПРАВЛЕНО: валидация цены и защита от null)
class AdCreate(BaseModel):
    title: str
    description: str
    price: float = Field(..., gt=0)  # Цена должна быть больше 0
    author: str


class AdUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    price: float | None = Field(None, gt=0)  # Цена должна быть больше 0, если передана
    author: str | None = None


class AdResponse(AdCreate):
    id: int
    created_at: datetime  # ИСПРАВЛЕНО: тип datetime

    class Config:
        from_attributes = True


# 5. Инициализация FastAPI
app = FastAPI(title="Advertisement Service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"message": "Сервис объявлений работает!"}


# --- CRUD ОПЕРАЦИИ ---

@app.post("/advertisement", response_model=AdResponse)
def create_ad(ad: AdCreate, db: Session = Depends(get_db)):
    new_ad = Advertisement(
        title=ad.title,
        description=ad.description,
        price=ad.price,
        author=ad.author
    )
    db.add(new_ad)
    db.commit()
    db.refresh(new_ad)
    return new_ad


@app.get("/advertisement", response_model=list[AdResponse])
def search_ads(
    title: str | None = Query(None),
    description: str | None = Query(None),
    author: str | None = None,
    min_price: float | None = None,
    created_at: str | None = None,
    db: Session = Depends(get_db)
):


@app.patch("/advertisement/{advertisement_id}", response_model=AdResponse)
def update_ad(advertisement_id: int, ad_update: AdUpdate, db: Session = Depends(get_db)):
    ad = db.query(Advertisement).filter(Advertisement.id == advertisement_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    update_data = ad_update.model_dump(exclude_unset=True)

    # ИСПРАВЛЕНО: защита от передачи null в поля
    if any(value is None for value in update_data.values()):
        raise HTTPException(status_code=422, detail="Fields cannot be null")

    for key, value in update_data.items():
        setattr(ad, key, value)

    db.commit()
    db.refresh(ad)
    return ad


@app.delete("/advertisement/{advertisement_id}")
def delete_ad(advertisement_id: int, db: Session = Depends(get_db)):
    ad = db.query(Advertisement).filter(Advertisement.id == advertisement_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    db.delete(ad)
    db.commit()
    return {"message": "Объявление удалено"}


# ИСПРАВЛЕНО: Поиск теперь по всем полям
@app.get("/advertisement", response_model=list[AdResponse])
def search_ads(
        title: str | None = None,
        description: str | None = None,
        author: str | None = None,
        min_price: float | None = None,
        created_at: str | None = None,
        db: Session = Depends(get_db)
):
    query = db.query(Advertisement)

    if title:
        query = query.filter(Advertisement.title.ilike(f"%{title}%"))
    if description:
        query = query.filter(Advertisement.description.ilike(f"%{description}%"))
    if author:
        query = query.filter(Advertisement.author.ilike(f"%{author}%"))
    if min_price is not None:
        query = query.filter(Advertisement.price >= min_price)
    if created_at:
        # Поиск по дате (сравниваем строковое представление или можно добавить логику)
        query = query.filter(Advertisement.created_at.cast(String).like(f"%{created_at}%"))

    return query.all()