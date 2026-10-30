import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, Numeric
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime
from pydantic import BaseModel

# 1. Загружаем переменные окружения из файла .env
load_dotenv()

# 2. Формируем строку подключения
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 3. Настройка SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 4. Модель базы данных (таблица в PostgreSQL)
class Advertisement(Base):
    __tablename__ = "advertisements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    author = Column(String, nullable=False)
    created_at = Column(String) # Пока строка, потом сделаем красиво

# Создаем таблицы в базе данных (если их нет)
Base.metadata.create_all(bind=engine)

# 5. Pydantic-схемы (для проверки данных от пользователя)
class AdCreate(BaseModel):
    title: str
    description: str
    price: float
    author: str

class AdUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    price: float | None = None
    author: str | None = None

class AdResponse(AdCreate):
    id: int
    created_at: str

    class Config:
        from_attributes = True

# 6. Инициализация FastAPI
app = FastAPI(title="Advertisement Service")

# Зависимость для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 7. Простой тестовый роут
@app.get("/")
def read_root():
    return {"message": "Сервис объявлений работает!"}


# --- CRUD ОПЕРАЦИИ ---

# 1. Создание объявления (POST)
@app.post("/advertisement", response_model=AdResponse)
def create_ad(ad: AdCreate, db: Session = Depends(get_db)):
    # Создаем объект модели из данных, которые прислал пользователь
    new_ad = Advertisement(
        title=ad.title,
        description=ad.description,
        price=ad.price,
        author=ad.author,
        created_at=datetime.now().isoformat()
    )
    db.add(new_ad)  # Добавляем в сессию
    db.commit()  # Сохраняем в базу
    db.refresh(new_ad)  # Обновляем объект (чтобы получить ID из базы)
    return new_ad


# 2. Получение объявления по ID (GET)
@app.get("/advertisement/{advertisement_id}", response_model=AdResponse)
def get_ad(advertisement_id: int, db: Session = Depends(get_db)):
    ad = db.query(Advertisement).filter(Advertisement.id == advertisement_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    return ad


# 3. Обновление объявления (PATCH)
@app.patch("/advertisement/{advertisement_id}", response_model=AdResponse)
def update_ad(advertisement_id: int, ad_update: AdUpdate, db: Session = Depends(get_db)):
    ad = db.query(Advertisement).filter(Advertisement.id == advertisement_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    # Обновляем только те поля, которые пришли
    update_data = ad_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ad, key, value)

    db.commit()
    db.refresh(ad)
    return ad


# 4. Удаление объявления (DELETE)
@app.delete("/advertisement/{advertisement_id}")
def delete_ad(advertisement_id: int, db: Session = Depends(get_db)):
    ad = db.query(Advertisement).filter(Advertisement.id == advertisement_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    db.delete(ad)
    db.commit()
    return {"message": "Объявление удалено"}


# 5. Поиск по полям (GET с Query String)
@app.get("/advertisement", response_model=list[AdResponse])
def search_ads(
        title: str | None = None,
        author: str | None = None,
        min_price: float | None = None,
        db: Session = Depends(get_db)
):
    query = db.query(Advertisement)

    if title:
        query = query.filter(Advertisement.title.ilike(f"%{title}%"))
    if author:
        query = query.filter(Advertisement.author.ilike(f"%{author}%"))
    if min_price is not None:
        query = query.filter(Advertisement.price >= min_price)

    return query.all()

