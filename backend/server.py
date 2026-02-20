"""
Budget Agent - FastAPI Server
Serves the cost analysis dashboard and API endpoints.
"""
import json
import os
import sys

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from tools import (
    get_agent_overview,
    find_hidden_costs,
    estimate_task_cost,
    get_cost_timeline,
    load_all_messages,
    extract_usage,
    classify_message,
)

app = FastAPI(title="Budget Agent API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/overview")
async def api_overview():
    """Get agent overview with costs."""
    try:
        result = get_agent_overview()
        return JSONResponse(content=json.loads(result))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/hidden-costs")
async def api_hidden_costs():
    """Find hidden costs in session data."""
    try:
        result = find_hidden_costs()
        return JSONResponse(content=json.loads(result))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/estimate")
async def api_estimate(task: str, model: str = "claude-sonnet-4-5"):
    """Estimate cost for a task."""
    try:
        result = estimate_task_cost(task, model)
        return JSONResponse(content=json.loads(result))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/timeline")
async def api_timeline():
    """Get cost timeline."""
    try:
        result = get_cost_timeline()
        return JSONResponse(content=json.loads(result))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/health")
async def health():
    """Health check."""
    messages = load_all_messages()
    return {"status": "ok", "total_messages": len(messages), "version": "2.0.0"}

# Serve frontend
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
async def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Frontend not found. API available at /api/overview, /api/hidden-costs, /api/timeline, /api/estimate?task=..."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
