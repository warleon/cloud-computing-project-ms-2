import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# ============================================================
# Cargar variables de entorno (.env)
# ============================================================
load_dotenv()

# En Docker Compose, el host debe ser el nombre del servicio (ms2_postgres)
DB_HOST = os.getenv("DB_HOST", "ms2_postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ms2_accounts")
DB_USER = os.getenv("DB_USER", "ms2")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")

# ============================================================
# Construir la URL de conexión
# ============================================================
SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ============================================================
# Configurar engine y sesión
# ============================================================
# echo=True → loguea las queries SQL (útil en desarrollo)
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False, future=True)

# sessionmaker crea sesiones de BD que serán usadas en dependencias
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ============================================================
# Base para los modelos ORM
# ============================================================
Base = declarative_base()

# ============================================================
# Dependencia para inyección en FastAPI
# ============================================================
def get_db():
    """
    Crea una sesión de base de datos.
    Se asegura de cerrarla correctamente tras cada request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
