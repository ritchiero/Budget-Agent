"""
Budget Agent - Cost Analysis Tools (Real Clawdbot Format)
Parses actual ~/.clawdbot/ session data to find hidden costs.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from strands import tool

PRICING = {
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-4-5": {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_write": 1.0},
}

def get_data_dir():
    return os.environ.get("OPENCLAW_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

def load_sessions():
    data_dir = get_data_dir()
    for fname in ["sessions_real.json", "sessions.json"]:
        path = os.path.join(data_dir, fname)
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    return {}

def classify_message(entry):
    """Classify a message by analyzing content for hidden cost patterns."""
    msg = entry.get("message", {})
    role = msg.get("role", "")
    raw_content = msg.get("content", "")
    content = ""
    if isinstance(raw_content, str):
        content = raw_content.lower()
    elif isinstance(raw_content, list):
        for block in raw_content:
            if isinstance(block, dict) and block.get("type") == "text":
                content += block.get("text", "").lower() + " "
            elif isinstance(block, dict) and block.get("type") == "thinking":
                content += block.get("thinking", "").lower() + " "
            elif isinstance(block, str):
                content += block.lower() + " "
    if any(kw in content for kw in ["heartbeat", "heartbeat_ok", "health check", "systems nominal",
                                      "all systems", "routine check"]):
        return "heartbeat"
    if any(kw in content for kw in ["whatsapp", "gateway disconnect", "reconnect", "status 428",
                                      "connection lost", "reconectando", "desconect"]):
        return "whatsapp_reconnect"
    if any(kw in content for kw in ["memory resync", "soul.md", "loading conversation",
                                      "context reload", "compaction", "summarizing history"]):
        return "memory_resync"
    if any(kw in content for kw in ["himalaya", "inbox", "email scan", "checking email",
                                      "new emails", "correo", "mail check"]):
        return "email_check"
    if any(kw in content for kw in ["cost report", "session cost", "daily usage", "token usage",
                                      "spending report", "costo de sesion"]):
        return "cost_report"
    if any(kw in content for kw in ["cron", "scheduled", "automated task", "periodic"]):
        return "cron_task"
    if role == "user":
        return "user_request"
    elif role == "assistant":
        return "response"
    return "other"

def extract_usage(entry):
    """Extract usage data from real Clawdbot message format."""
    msg = entry.get("message", {})
    usage = msg.get("usage", {})
    if not usage:
        return None
    cost_data = usage.get("cost", {})
    return {
        "input": usage.get("input", 0),
        "output": usage.get("output", 0),
        "cache_read": usage.get("cacheRead", 0),
        "cache_write": usage.get("cacheWrite", 0),
        "total_tokens": usage.get("totalTokens", 0) or (usage.get("input", 0) + usage.get("output", 0)),
        "cost": {
            "input": cost_data.get("input", 0),
            "output": cost_data.get("output", 0),
            "cache_read": cost_data.get("cacheRead", 0),
            "cache_write": cost_data.get("cacheWrite", 0),
            "total": cost_data.get("total", 0),
        }
    }

def load_all_messages():
    """Load all message entries from all .jsonl files."""
    data_dir = get_data_dir()
    all_entries = []
    for f in sorted(Path(data_dir).glob("*.jsonl")):
        with open(f, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "message":
                        entry["_source_file"] = f.name
                        all_entries.append(entry)
                except json.JSONDecodeError:
                    continue
    return all_entries


@tool
def get_agent_overview() -> str:
    """Get overview of all Clawdbot sessions with token usage and costs.
    Use when user asks about agents, overall usage, or wants a summary.
    Returns:
        str: JSON overview of all agents and sessions
    """
    sessions = load_sessions()
    messages = load_all_messages()
    file_costs = {}
    total_cost = 0
    total_tokens = 0
    total_messages = 0
    for entry in messages:
        usage = extract_usage(entry)
        if not usage:
            continue
        source = entry.get("_source_file", "unknown")
        if source not in file_costs:
            file_costs[source] = {"cost": 0, "tokens": 0, "messages": 0, "model": "unknown"}
        file_costs[source]["cost"] += usage["cost"]["total"]
        file_costs[source]["tokens"] += usage["total_tokens"]
        file_costs[source]["messages"] += 1
        file_costs[source]["model"] = entry.get("message", {}).get("model", file_costs[source]["model"])
        total_cost += usage["cost"]["total"]
        total_tokens += usage["total_tokens"]
        total_messages += 1
    session_overview = []
    for key, data in sessions.items():
        agent_name = key.split(":")[1] if ":" in key else key
        session_type = "cron" if "cron" in key else "main"
        delivery = data.get("deliveryContext", {})
        session_overview.append({
            "session_key": key,
            "agent": agent_name,
            "type": session_type,
            "channel": delivery.get("channel", "unknown"),
            "compaction_count": data.get("compactionCount", 0),
        })
    top_sessions = sorted(file_costs.items(), key=lambda x: x[1]["cost"], reverse=True)[:10]
    return json.dumps({
        "sessions": session_overview,
        "total_sessions": len(sessions),
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "total_messages": total_messages,
        "total_jsonl_files": len(file_costs),
        "top_spending_sessions": [
            {"file": k, "cost_usd": round(v["cost"], 4), "tokens": v["tokens"],
             "messages": v["messages"], "model": v["model"]}
            for k, v in top_sessions
        ],
    }, indent=2)


@tool
def find_hidden_costs() -> str:
    """Analyze all Clawdbot session logs to find hidden/wasteful token consumption.
    Classifies every message by content to detect: heartbeats, memory resyncs,
    WhatsApp reconnects, email scans, cost reports, cron tasks vs actual user requests.
    Returns:
        str: JSON analysis with categories, totals, and actionable recommendations
    """
    messages = load_all_messages()
    categories = {
        "heartbeat": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                      "description": "Health check pings (WhatsApp, himalaya, cron)"},
        "memory_resync": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                          "description": "SOUL.md + conversation history reloads"},
        "whatsapp_reconnect": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                               "description": "WhatsApp gateway disconnect/reconnect"},
        "email_check": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                        "description": "Himalaya IMAP inbox scans"},
        "cost_report": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                        "description": "Auto cost report generation"},
        "cron_task": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                      "description": "Scheduled/cron tasks"},
        "user_request": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                         "description": "Your actual requests"},
        "response": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                     "description": "Agent responses to you"},
        "other": {"count": 0, "tokens": 0, "cost": 0, "cache_read": 0,
                  "description": "Unclassified"},
    }
    total_cache_read_cost = 0
    total_cache_write_cost = 0
    timestamps = []
    for entry in messages:
        usage = extract_usage(entry)
        if not usage:
            continue
        cat = classify_message(entry)
        if cat not in categories:
            cat = "other"
        categories[cat]["count"] += 1
        categories[cat]["tokens"] += usage["total_tokens"]
        categories[cat]["cost"] += usage["cost"]["total"]
        categories[cat]["cache_read"] += usage["cache_read"]
        total_cache_read_cost += usage["cost"]["cache_read"]
        total_cache_write_cost += usage["cost"]["cache_write"]
        ts = entry.get("timestamp")
        if ts:
            timestamps.append(ts)
    user_cost = sum(categories[c]["cost"] for c in ["user_request", "response"])
    hidden_cost = sum(categories[c]["cost"] for c in categories if c not in ["user_request", "response"])
    total_cost = user_cost + hidden_cost
    waste_pct = (hidden_cost / total_cost * 100) if total_cost > 0 else 0
    if timestamps:
        timestamps_s = []
        for t in timestamps:
            if isinstance(t, str):
                try:
                    from datetime import datetime as dt
                    timestamps_s.append(dt.fromisoformat(t.replace("Z", "+00:00")).timestamp())
                except Exception:
                    pass
            elif isinstance(t, (int, float)):
                timestamps_s.append(t / 1000 if t > 1e12 else t)
        if timestamps_s:
            active_days = max((max(timestamps_s) - min(timestamps_s)) / 86400, 1)
        else:
            active_days = 14
    else:
        active_days = 14
    daily_cost = total_cost / active_days
    monthly_total = daily_cost * 30
    monthly_hidden = (hidden_cost / active_days) * 30
    recommendations = []
    def rec(cat_key, issue, fix, savings_pct):
        if categories[cat_key]["cost"] > 0:
            monthly = (categories[cat_key]["cost"] / active_days) * 30
            recommendations.append({"issue": issue, "monthly_waste": round(monthly, 2),
                                    "fix": fix, "savings_pct": savings_pct})
    rec("heartbeat", "Heartbeat overhead - LLM health checks burning tokens 24/7",
        "Replace LLM heartbeats with HTTP pings. Only invoke model when action needed.", 80)
    rec("memory_resync", "Full memory resyncs reloading SOUL.md + history",
        "Cache SOUL.md locally. Incremental history loading. Only full resync after reconnects.", 60)
    rec("whatsapp_reconnect", "WhatsApp reconnects invoking the LLM",
        "Handle reconnects at transport layer. Simple state machine, no LLM needed.", 95)
    rec("email_check", "Himalaya email scans using LLM to check inbox",
        "Use himalaya CLI directly. Only invoke LLM when emails need processing/response.", 75)
    rec("cost_report", "Auto cost reports using LLM for arithmetic",
        "Generate cost reports with bash script. Zero token cost for math.", 100)
    rec("cron_task", "Cron tasks consuming tokens on schedule",
        "Gate cron tasks behind lightweight checks. Only invoke LLM when action is needed.", 50)
    if total_cache_read_cost > 0:
        cache_monthly = (total_cache_read_cost / active_days) * 30
        if cache_monthly > 0.01:
            recommendations.append({
                "issue": "Cache read overhead: ${:.2f}/mo".format(cache_monthly),
                "monthly_waste": round(cache_monthly, 2),
                "fix": "Oversized system prompts or history re-sent each turn. Trim prompt, use sliding window.",
                "savings_pct": 40
            })
    potential_savings = sum(r["monthly_waste"] * r["savings_pct"] / 100 for r in recommendations)
    return json.dumps({
        "cost_breakdown": {
            k: {"count": v["count"], "tokens": v["tokens"], "cache_read": v["cache_read"],
                "cost_usd": round(v["cost"], 4), "description": v["description"]}
            for k, v in categories.items() if v["count"] > 0
        },
        "summary": {
            "total_cost": round(total_cost, 4),
            "user_initiated_cost": round(user_cost, 4),
            "hidden_cost": round(hidden_cost, 4),
            "waste_percentage": round(waste_pct, 1),
            "active_days_analyzed": round(active_days, 1),
            "daily_avg_cost": round(daily_cost, 4),
            "projected_monthly_total": round(monthly_total, 2),
            "projected_monthly_hidden": round(monthly_hidden, 2),
            "cache_read_cost": round(total_cache_read_cost, 4),
            "cache_write_cost": round(total_cache_write_cost, 4),
        },
        "recommendations": recommendations,
        "total_potential_monthly_savings": round(potential_savings, 2)
    }, indent=2)


@tool
def estimate_task_cost(task_description: str, model: str = "claude-sonnet-4-5") -> str:
    """Pre-estimate the cost of a task before executing it, based on historical Clawdbot data.
    Args:
        task_description: What the task is (e.g., "research competitors", "draft email")
        model: Model to estimate for (default: claude-sonnet-4-5)
    Returns:
        str: JSON with estimated tokens, cost, time, and cheaper alternatives
    """
    messages = load_all_messages()
    assistant_costs = []
    for entry in messages:
        usage = extract_usage(entry)
        if not usage or entry.get("message", {}).get("role") != "assistant":
            continue
        assistant_costs.append(usage)
    if assistant_costs:
        avg_input = sum(u["input"] for u in assistant_costs) / len(assistant_costs)
        avg_output = sum(u["output"] for u in assistant_costs) / len(assistant_costs)
        avg_cache = sum(u["cache_read"] for u in assistant_costs) / len(assistant_costs)
        avg_cost = sum(u["cost"]["total"] for u in assistant_costs) / len(assistant_costs)
    else:
        avg_input, avg_output, avg_cache, avg_cost = 8000, 1500, 50000, 0.03
    task_lower = task_description.lower()
    if any(w in task_lower for w in ["research", "investigate", "analyze", "deep dive", "compare"]):
        mult, complexity, est_time, est_tools = 4.0, "high", "3-8 min", 8
    elif any(w in task_lower for w in ["email", "draft", "write", "reply", "correo"]):
        mult, complexity, est_time, est_tools = 1.5, "medium", "30-90s", 2
    elif any(w in task_lower for w in ["check", "status", "list", "show", "revisar"]):
        mult, complexity, est_time, est_tools = 0.8, "low", "10-30s", 1
    elif any(w in task_lower for w in ["summarize", "recap", "resumen"]):
        mult, complexity, est_time, est_tools = 2.5, "medium-high", "1-3 min", 3
    elif any(w in task_lower for w in ["browse", "search", "find", "buscar"]):
        mult, complexity, est_time, est_tools = 3.0, "medium", "2-5 min", 5
    else:
        mult, complexity, est_time, est_tools = 1.5, "medium", "1-3 min", 3
    est_cost = avg_cost * mult
    overhead_cost = 0.014 * (mult * 2)
    total = est_cost + overhead_cost
    alternatives = {}
    for alt_model, alt_p in PRICING.items():
        if alt_model != model and alt_model != "claude-sonnet-4-20250514":
            alt_cost = ((avg_input * mult / 1e6) * alt_p["input"] +
                        (avg_output * mult / 1e6) * alt_p["output"] +
                        (avg_cache / 1e6) * alt_p["cache_read"])
            alternatives[alt_model] = round(alt_cost, 4)
    return json.dumps({
        "task": task_description,
        "complexity": complexity,
        "model": model,
        "estimate": {
            "input_tokens": int(avg_input * mult),
            "output_tokens": int(avg_output * mult),
            "task_cost_usd": round(est_cost, 4),
            "overhead_cost_usd": round(overhead_cost, 4),
            "total_cost_usd": round(total, 4),
            "estimated_tool_calls": est_tools,
            "estimated_time": est_time,
        },
        "based_on": {"avg_response_cost": round(avg_cost, 4), "sample_size": len(assistant_costs)},
        "alternative_models": alternatives,
        "cheapest_option": min(alternatives.items(), key=lambda x: x[1]) if alternatives else None,
    }, indent=2)


@tool
def get_cost_timeline() -> str:
    """Get timeline of costs across all sessions. Shows cumulative spending and cost spikes.
    Returns:
        str: JSON timeline with timestamps, categories, and daily totals
    """
    messages = load_all_messages()
    timeline = []
    for entry in messages:
        usage = extract_usage(entry)
        if not usage:
            continue
        ts_raw = entry.get("timestamp", "")
        if isinstance(ts_raw, str) and ts_raw:
            try:
                from datetime import datetime as dt
                ts = dt.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp()
            except Exception:
                ts = 0
        elif isinstance(ts_raw, (int, float)):
            ts = ts_raw / 1000 if ts_raw > 1e12 else ts_raw
        else:
            ts = 0
        timeline.append({
            "timestamp": ts,
            "category": classify_message(entry),
            "cost_usd": usage["cost"]["total"],
            "tokens": usage["total_tokens"],
            "input_tokens": usage["input"],
            "output_tokens": usage["output"],
            "cache_read_tokens": usage["cache_read"],
            "model": entry.get("message", {}).get("model", "unknown"),
            "source_file": entry.get("_source_file", "unknown"),
        })
    timeline.sort(key=lambda x: x["timestamp"])
    cumulative = 0
    daily_costs = {}
    for e in timeline:
        cumulative += e["cost_usd"]
        e["cumulative_cost_usd"] = round(cumulative, 4)
        if e["timestamp"]:
            try:
                day = datetime.fromtimestamp(e["timestamp"]).strftime("%Y-%m-%d")
                daily_costs[day] = daily_costs.get(day, 0) + e["cost_usd"]
            except (ValueError, OSError):
                pass
    most_expensive = max(daily_costs.items(), key=lambda x: x[1]) if daily_costs else ("unknown", 0)
    return json.dumps({
        "timeline": timeline[-50:],
        "total_entries": len(timeline),
        "total_cost": round(cumulative, 4),
        "daily_costs": {k: round(v, 4) for k, v in sorted(daily_costs.items())},
        "most_expensive_day": {"date": most_expensive[0], "cost_usd": round(most_expensive[1], 4)},
        "total_days": len(daily_costs),
    }, indent=2)
