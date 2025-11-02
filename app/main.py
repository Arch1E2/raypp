from fastapi import FastAPI
from app.api.routes import router
from app.db.database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RayPP API",
    description="FastAPI application with PostgreSQL, ChromaDB, and Redis",
    version="1.0.0"
)

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Welcome to RayPP API",
        "docs": "/docs",
        "health": "/api/health"
    }
