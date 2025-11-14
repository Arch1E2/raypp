from fastapi import FastAPI

from src.router.base_route import router as api_router

app = FastAPI(
    title="raypp-src-sample",
    description="Minimal FastAPI app for RayPP (sample)",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "src-sample"}