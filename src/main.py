from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Importamos la base y el engine de SQLAlchemy
from .database import Base, engine
# Importamos los routers
from .routers import accounts, ledger, internal

# ============================================================
# Configuración de la aplicación
# ============================================================
app = FastAPI(
    title="MS2 - Accounts Service",
    description="""
Microservicio **MS2 - Accounts**  
Parte del proyecto Cloud Computing (Banco).

### Funcionalidades principales:
- **Gestión de cuentas bancarias**:
  - Crear cuentas nuevas asociadas a clientes.
  - Consultar información detallada de cuentas.
  - Actualizar el estado de las cuentas (ACTIVA, BLOQUEADA, CERRADA).
  - Obtener saldo disponible en la cuenta.
- **Ledger (movimientos contables)**:
  - Consultar el historial de movimientos (débitos y créditos).
- **Integración interna**:
  - Endpoint de transferencia, consumido por el MS3 (Transacciones),
    ejecutando débitos y créditos de manera atómica.

> **Swagger/OpenAPI** disponible en `/docs`  
> **Healthcheck** disponible en `/healthz`
    """,
    version="1.0.0",
    contact={
        "name": "Cloud Computing Team - MS2",
        "url": "https://github.com/warleon/cloud-computing-project",
    },
)

# ============================================================
# Configuración CORS
# ============================================================
# Permite orígenes definidos en variable de entorno ALLOWED_ORIGINS
origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Inicialización de Base de Datos
# ============================================================
# Crea las tablas automáticamente si no existen.
# En producción se recomienda usar Alembic para migraciones controladas.
Base.metadata.create_all(bind=engine)

# ============================================================
# Routers
# ============================================================
# Endpoints organizados por responsabilidad
app.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
app.include_router(ledger.router, prefix="/ledger", tags=["Ledger"])
app.include_router(internal.router, prefix="/internal", tags=["Internal"])

# ============================================================
# Endpoints de sistema
# ============================================================
@app.get("/healthz", tags=["System"])
def health_check():
    """
    Verifica la salud del servicio.
    Retorna 200 si el microservicio está corriendo correctamente.
    """
    return {"status": "ok", "service": "MS2 - Accounts"}

@app.get("/", tags=["System"])
def root():
    """
    Endpoint raíz del microservicio.
    Útil como mensaje de bienvenida.
    """
    return {
        "message": "Bienvenido al MS2 - Accounts Service",
        "swagger_ui": "/docs",
        "healthcheck": "/healthz"
    }
