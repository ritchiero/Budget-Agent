"""
Agent Cost Auditor - API Server
Serves the web dashboard and handles agent chat requests.
"""
import os
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from agent import create_agent
from tools import get_agent_overview, find_hidden_costs, estimate_task_cost, get_cost_timeline

app = FastAPI(title="Agent Cost Auditor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create agent once
agent = None

def get_or_create_agent():
    global agent
    if agent is None:
        agent = create_agent()
    return agent


@app.get("/api/overview")
async def api_overview():
    """Get agent overview data for the dashboard."""
    try:
        data = get_agent_overview.tool_handler(tool_use_id="api", input={})
        result = json.loads(data["content"][0]["text"])
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/hidden-costs")
async def api_hidden_costs():
    """Get hidden costs analysis."""
    try:
        data = find_hidden_costs.tool_handler(tool_use_id="api", input={})
        result = json.loads(data["content"][0]["text"])
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/timeline")
async def api_timeline():
    """Get cost timeline."""
    try:
        data = get_cost_timeline.tool_handler(tool_use_id="api", input={})
        result = json.loads(data["content"][0]["text"])
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/chat")
async def api_chat(request: Request):
    """Chat with the cost auditor agent."""
    try:
        body = await request.json()
        message = body.get("message", "")
        
        if not message:
            return JSONResponse(content={"error": "No message provided"}, status_code=400)
        
        a = get_or_create_agent()
        result = a(message)
        
        return JSONResponse(content={
            "response": str(result),
            "usage": {
                "input_tokens": result.metrics.get("inputTokens", 0) if hasattr(result, 'metrics') else 0,
                "output_tokens": result.metrics.get("outputTokens", 0) if hasattr(result, 'metrics') else 0,
            }
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e), "response": f"Error: {str(e)}"}, status_code=500)


@app.get("/api/estimate")
async def api_estimate(task: str, model: str = "claude-sonnet-4-20250514"):
    """Estimate cost for a task."""
    try:
        data = estimate_task_cost.tool_handler(
            tool_use_id="api",
            input={"task_description": task, "model": model}
        )
        result = json.loads(data["content"][0]["text"])
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# Serve frontend
@app.get("/")
async def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    return FileResponse(frontend_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
