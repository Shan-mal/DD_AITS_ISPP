from models.models import Base
from core.database import engine

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Таблицы успешно созданы.")