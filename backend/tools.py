"""
OpenClaw Cost Auditor - Custom tools for Strands Agent
Analyzes OpenClaw session data to find hidden costs and optimize spending.
"""
import json
import os
from pathlib import Path
from strands import tool

# Pricing per million tokens (as of Feb 2026)
PRICING = {
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0, "cache_read": 0.30},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.30},
    "claude-opus-4-5-20250414": {"input": 15.0, "output": 75.0, "cache_read": 1.50},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0, "cache_read": 0.08},
    "gpt-5.2": {"input": 2.50, "output": 10.0, "cache_read": 0.0},
    "gpt-5.3-codex-spark": {"input": 5.0, "output": 15.0, "cache_read": 0.0},
}

def get_data_dir():
    """Get the data directory path."""
    return os.environ.get("OPENCLAW_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

def load_sessions():
    """Load OpenClaw sessions.json data."""
    data_dir = get_data_dir()
    sessions_path = os.path.join(data_dir, "sessions.json")
    with open(sessions_path, "r") as f:
        return json.load(f)

def load_session_logs():
    """Load all JSONL session log files."""
    data_dir = get_data_dir()
    all_messages = []
    for f in Path(data_dir).glob("*.jsonl"):
        with open(f, "r") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        all_messages.append(json.load(open("/dev/stdin") if False else None) if False else json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return all_messages

def calculate_cost(usage, model):
    """Calculate cost for a single message."""
    pricing = PRICING.get(model, PRICING["claude-sonnet-4-20250514"])
    input_cost = (usage.get("input", 0) / 1_000_000) * pricing["input"]
    output_cost = (usage.get("output", 0) / 1_000_000) * pricing["output"]
    cache_cost = (usage.get("cacheRead", 0) / 1_000_000) * pricing["cache_read"]
    return input_cost + output_cost + cache_cost


@tool
def get_agent_overview() -> str:
    """Get an overview of all OpenClaw agents with their token usage, costs, and activity.
    Use this when the user asks about their agents, overall usage, or wants a summary.
    
    Returns:
        str: JSON formatted overview of all agents
    """
    sessions = load_sessions()
    overview = []
    total_cost = 0
    
    for agent_key, data in sessions.items():
        agent_name = agent_key.split(":")[1] if ":" in agent_key else agent_key
        model = data.get("model", "unknown")
        pricing = PRICING.get(model, PRICING["claude-sonnet-4-20250514"])
        
        input_cost = (data.get("totalInputTokens", 0) / 1_000_000) * pricing["input"]
        output_cost = (data.get("totalOutputTokens", 0) / 1_000_000) * pricing["output"]
        cache_cost = (data.get("totalCacheRead", 0) / 1_000_000) * pricing["cache_read"]
        agent_cost = input_cost + output_cost + cache_cost
        total_cost += agent_cost
        
        overview.append({
            "agent": agent_name,
            "model": model,
            "total_tokens": data.get("totalTokens", 0),
            "input_tokens": data.get("totalInputTokens", 0),
            "output_tokens": data.get("totalOutputTokens", 0),
            "cache_read_tokens": data.get("totalCacheRead", 0),
            "sessions": data.get("sessionCount", 0),
            "estimated_cost_usd": round(agent_cost, 4),
            "last_active": data.get("lastActive", "unknown")
        })
    
    return json.dumps({
        "agents": overview,
        "total_estimated_cost_usd": round(total_cost, 4),
        "total_agents": len(overview)
    }, indent=2)


@tool
def find_hidden_costs() -> str:
    """Analyze OpenClaw session logs to find hidden/wasteful token consumption.
    Identifies: heartbeats, memory resyncs, tool retries, context compactions, 
    system prompt reloads, and other non-user-initiated token usage.
    
    Returns:
        str: JSON analysis of hidden costs with categories and recommendations
    """
    data_dir = get_data_dir()
    
    categories = {
        "heartbeats": {"count": 0, "tokens": 0, "cost": 0, "description": "Health check pings (WhatsApp status, himalaya inbox, cron jobs) every 60s"},
        "memory_resyncs": {"count": 0, "tokens": 0, "cost": 0, "description": "SOUL.md + conversation history reloads"},
        "whatsapp_reconnects": {"count": 0, "tokens": 0, "cost": 0, "description": "WhatsApp gateway disconnect/reconnect cycles (status 428)"},
        "email_checks": {"count": 0, "tokens": 0, "cost": 0, "description": "Himalaya IMAP inbox scans for new emails"},
        "compactions": {"count": 0, "tokens": 0, "cost": 0, "description": "Context window compaction/summarization"},
        "cost_reports": {"count": 0, "tokens": 0, "cost": 0, "description": "Auto-generated cost report calculations"},
        "tool_retries": {"count": 0, "tokens": 0, "cost": 0, "description": "Failed tool calls that retry and waste tokens"},
        "system_prompts": {"count": 0, "tokens": 0, "cost": 0, "description": "System prompt reloads"},
        "user_requests": {"count": 0, "tokens": 0, "cost": 0, "description": "Actual user-initiated requests"},
        "responses": {"count": 0, "tokens": 0, "cost": 0, "description": "Agent responses to user requests"}
    }
    
    for f in Path(data_dir).glob("*.jsonl"):
        with open(f, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                if entry.get("type") != "message":
                    continue
                
                msg = entry.get("message", {})
                usage = msg.get("usage", {})
                tags = entry.get("tags", [])
                cost = usage.get("cost", {}).get("total", 0)
                tokens = usage.get("input", 0) + usage.get("output", 0)
                
                if "heartbeat" in tags:
                    cat = "heartbeats"
                elif "memory_resync" in tags:
                    cat = "memory_resyncs"
                elif "whatsapp_reconnect" in tags:
                    cat = "whatsapp_reconnects"
                elif "email_check" in tags:
                    cat = "email_checks"
                elif "tool_retry" in tags:
                    cat = "tool_retries"
                elif "compaction" in tags:
                    cat = "compactions"
                elif "cost_report" in tags:
                    cat = "cost_reports"
                elif "system_prompt" in tags:
                    cat = "system_prompts"
                elif "user_request" in tags:
                    cat = "user_requests"
                elif "response" in tags:
                    cat = "responses"
                else:
                    continue
                
                categories[cat]["count"] += 1
                categories[cat]["tokens"] += tokens
                categories[cat]["cost"] += cost
    
    # Calculate waste
    user_cost = categories["user_requests"]["cost"] + categories["responses"]["cost"]
    hidden_cost = sum(c["cost"] for k, c in categories.items() if k not in ["user_requests", "responses"])
    total_cost = user_cost + hidden_cost
    waste_percentage = (hidden_cost / total_cost * 100) if total_cost > 0 else 0
    
    # Monthly projections (assume this data is from ~1 day)
    monthly_hidden = hidden_cost * 30
    monthly_total = total_cost * 30
    
    recommendations = []
    if categories["heartbeats"]["cost"] > 0:
        hb_monthly = categories["heartbeats"]["cost"] * 30
        recommendations.append({
            "issue": "Heartbeat overhead — 60s interval burning tokens 24/7",
            "monthly_waste": round(hb_monthly, 2),
            "fix": "Increase heartbeat interval from 60s to 300s during idle periods. Use lightweight HTTP ping instead of LLM-powered health checks. Saves ~80% of heartbeat costs.",
            "savings_pct": 80
        })
    if categories["memory_resyncs"]["cost"] > 0:
        mr_monthly = categories["memory_resyncs"]["cost"] * 30
        recommendations.append({
            "issue": "Full memory resyncs loading entire SOUL.md + history",
            "monthly_waste": round(mr_monthly, 2),
            "fix": "Cache SOUL.md locally and only resync on config change. Use incremental history loading instead of full reload. Resync only after WhatsApp reconnects, not on schedule.",
            "savings_pct": 60
        })
    if categories["whatsapp_reconnects"]["cost"] > 0:
        wr_monthly = categories["whatsapp_reconnects"]["cost"] * 30
        recommendations.append({
            "issue": "WhatsApp gateway reconnect cycles (status 428)",
            "monthly_waste": round(wr_monthly, 2),
            "fix": "Handle reconnects at transport layer without invoking the LLM. Use simple connection state machine instead of asking the model to process disconnects.",
            "savings_pct": 95
        })
    if categories["email_checks"]["cost"] > 0:
        ec_monthly = categories["email_checks"]["cost"] * 30
        recommendations.append({
            "issue": "Himalaya email scans using LLM to check inbox",
            "monthly_waste": round(ec_monthly, 2),
            "fix": "Use himalaya CLI directly to count new emails. Only invoke LLM when there ARE emails to process. Skip newsletters/promotional with server-side filter rules.",
            "savings_pct": 75
        })
    if categories["compactions"]["cost"] > 0:
        cp_monthly = categories["compactions"]["cost"] * 30
        recommendations.append({
            "issue": "Context compaction using expensive model",
            "monthly_waste": round(cp_monthly, 2),
            "fix": "Use Haiku ($0.80/M input) instead of Sonnet ($3/M input) for compaction. Switch to sliding window instead of full re-summarization.",
            "savings_pct": 70
        })
    if categories["cost_reports"]["cost"] > 0:
        cr_monthly = categories["cost_reports"]["cost"] * 30
        recommendations.append({
            "issue": "Auto cost reports using LLM to compute arithmetic",
            "monthly_waste": round(cr_monthly, 2),
            "fix": "Generate cost reports with a bash script (like openclaw-token-tracker). Zero token cost for pure arithmetic.",
            "savings_pct": 100
        })
    if categories["tool_retries"]["cost"] > 0:
        tr_monthly = categories["tool_retries"]["cost"] * 30
        recommendations.append({
            "issue": "Tool call retries",
            "monthly_waste": round(tr_monthly, 2),
            "fix": "Add connection pooling and timeout handling. Implement circuit breaker pattern for flaky tools.",
            "savings_pct": 90
        })
    if categories["system_prompts"]["cost"] > 0:
        sp_monthly = categories["system_prompts"]["cost"] * 30
        recommendations.append({
            "issue": "System prompt reloads",
            "monthly_waste": round(sp_monthly, 2),
            "fix": "Cache system prompt in session. Only reload on config change.",
            "savings_pct": 95
        })
    
    return json.dumps({
        "cost_breakdown": {k: {"count": v["count"], "tokens": v["tokens"], "cost_usd": round(v["cost"], 4), "description": v["description"]} for k, v in categories.items()},
        "summary": {
            "total_cost_today": round(total_cost, 4),
            "user_initiated_cost": round(user_cost, 4),
            "hidden_cost": round(hidden_cost, 4),
            "waste_percentage": round(waste_percentage, 1),
            "projected_monthly_total": round(monthly_total, 2),
            "projected_monthly_hidden": round(monthly_hidden, 2)
        },
        "recommendations": recommendations,
        "total_potential_monthly_savings": round(sum(r["monthly_waste"] * r["savings_pct"] / 100 for r in recommendations), 2)
    }, indent=2)


@tool
def estimate_task_cost(task_description: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Pre-estimate the cost of running a task before executing it.
    Based on historical patterns from OpenClaw session data.
    
    Args:
        task_description: Description of the task to estimate (e.g., "research competitors", "draft email", "summarize document")
        model: The model to use for estimation (default: claude-sonnet-4-20250514)
    
    Returns:
        str: JSON with estimated tokens, cost, and time
    """
    # Task complexity heuristics based on common OpenClaw patterns
    task_lower = task_description.lower()
    
    if any(w in task_lower for w in ["research", "investigate", "analyze", "deep dive", "compare"]):
        est_input = 50000
        est_output = 12000
        est_tools = 8
        est_time = "3-8 minutes"
        complexity = "high"
    elif any(w in task_lower for w in ["email", "draft", "write", "reply", "message"]):
        est_input = 15000
        est_output = 3000
        est_tools = 2
        est_time = "30-90 seconds"
        complexity = "medium"
    elif any(w in task_lower for w in ["check", "status", "list", "show", "what"]):
        est_input = 5000
        est_output = 800
        est_tools = 1
        est_time = "10-30 seconds"
        complexity = "low"
    elif any(w in task_lower for w in ["summarize", "recap", "brief"]):
        est_input = 35000
        est_output = 5000
        est_tools = 3
        est_time = "1-3 minutes"
        complexity = "medium-high"
    elif any(w in task_lower for w in ["browse", "search", "find", "look up"]):
        est_input = 25000
        est_output = 4000
        est_tools = 5
        est_time = "2-5 minutes"
        complexity = "medium"
    else:
        est_input = 20000
        est_output = 4000
        est_tools = 3
        est_time = "1-3 minutes"
        complexity = "medium"
    
    # Add overhead costs
    overhead_heartbeats = 2450 * 2  # ~2 heartbeats during task
    overhead_memory = 18500  # one memory resync
    overhead_system = 8900  # system prompt
    
    total_input = est_input + overhead_heartbeats + overhead_memory + overhead_system
    total_output = est_output + 12 * 2 + 2200  # heartbeat + memory outputs
    
    pricing = PRICING.get(model, PRICING["claude-sonnet-4-20250514"])
    task_cost = (est_input / 1_000_000) * pricing["input"] + (est_output / 1_000_000) * pricing["output"]
    overhead_cost = ((total_input - est_input) / 1_000_000) * pricing["input"] + ((total_output - est_output) / 1_000_000) * pricing["output"]
    total_cost = task_cost + overhead_cost
    
    # Alternative model comparison
    alternatives = {}
    for alt_model, alt_pricing in PRICING.items():
        if alt_model != model:
            alt_cost = (total_input / 1_000_000) * alt_pricing["input"] + (total_output / 1_000_000) * alt_pricing["output"]
            alternatives[alt_model] = round(alt_cost, 4)
    
    return json.dumps({
        "task": task_description,
        "complexity": complexity,
        "model": model,
        "estimate": {
            "task_tokens": {"input": est_input, "output": est_output},
            "overhead_tokens": {"input": total_input - est_input, "output": total_output - est_output},
            "total_tokens": total_input + total_output,
            "task_cost_usd": round(task_cost, 4),
            "overhead_cost_usd": round(overhead_cost, 4),
            "total_cost_usd": round(total_cost, 4),
            "overhead_percentage": round(overhead_cost / total_cost * 100, 1) if total_cost > 0 else 0,
            "estimated_tool_calls": est_tools,
            "estimated_time": est_time
        },
        "alternative_models": alternatives,
        "cheapest_option": min(alternatives.items(), key=lambda x: x[1]) if alternatives else None
    }, indent=2)


@tool  
def get_cost_timeline() -> str:
    """Get a timeline of costs over the session, showing when money was spent and on what.
    Useful for identifying cost spikes and patterns.
    
    Returns:
        str: JSON timeline of costs with timestamps
    """
    data_dir = get_data_dir()
    timeline = []
    
    for f in Path(data_dir).glob("*.jsonl"):
        with open(f, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                if entry.get("type") != "message":
                    continue
                
                msg = entry.get("message", {})
                usage = msg.get("usage", {})
                tags = entry.get("tags", [])
                
                if not usage:
                    continue
                
                cost = usage.get("cost", {}).get("total", 0)
                timestamp = msg.get("timestamp", 0)
                
                category = "other"
                if "heartbeat" in tags: category = "heartbeat"
                elif "memory_resync" in tags: category = "memory_resync"
                elif "tool_retry" in tags: category = "tool_retry"
                elif "compaction" in tags: category = "compaction"
                elif "system_prompt" in tags: category = "system_prompt"
                elif "user_request" in tags: category = "user_request"
                elif "response" in tags: category = "response"
                
                timeline.append({
                    "timestamp": timestamp,
                    "category": category,
                    "cost_usd": cost,
                    "tokens": usage.get("input", 0) + usage.get("output", 0),
                    "input_tokens": usage.get("input", 0),
                    "output_tokens": usage.get("output", 0)
                })
    
    timeline.sort(key=lambda x: x["timestamp"])
    
    cumulative = 0
    for entry in timeline:
        cumulative += entry["cost_usd"]
        entry["cumulative_cost_usd"] = round(cumulative, 4)
    
    return json.dumps({
        "timeline": timeline,
        "total_entries": len(timeline),
        "total_cost": round(cumulative, 4)
    }, indent=2)
