from fastapi import FastAPI

app = FastAPI(title="Integration Copilot API", version="0.1.0")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
