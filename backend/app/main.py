from fastapi import FastAPI

from app.api.routes import ingest
from app.database import Base, engine

app = FastAPI(title="Content Creator Agentic ETL", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(ingest.router)
