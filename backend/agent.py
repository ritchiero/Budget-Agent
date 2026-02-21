"""
Agent Cost Auditor - Main Strands Agent
Analyzes OpenClaw/AI agent costs, finds hidden spending, and recommends optimizations.
Built with Strands Agents + Amazon Bedrock + Datadog LLM Observability.
"""
import os
import json
from strands import Agent
from strands.models.anthropic import AnthropicModel
from strands.telemetry.config import StrandsTelemetry
from tools import get_agent_overview, find_hidden_costs, estimate_task_cost, get_cost_timeline

# --- Datadog LLM Observability Setup ---
def setup_datadog_telemetry():
    """Configure OpenTelemetry to send traces to Datadog."""
    dd_api_key = os.environ.get("DD_API_KEY", "")
    dd_site = os.environ.get("DD_SITE", "us5.datadoghq.com")
    if dd_api_key:
        os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"
        os.environ["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] = "http/protobuf"
        os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = f"https://otlp.{dd_site}/v1/traces"
        os.environ["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = f"dd-api-key={dd_api_key},dd-otlp-source=llmobs"
        telemetry = StrandsTelemetry()
        telemetry.setup_otlp_exporter()
        print(f"Datadog LLM Observability configured -> {dd_site}")
    else:
        print("DD_API_KEY not set. Running without Datadog telemetry.")

# --- Agent Setup ---
SYSTEM_PROMPT = """You are the Agent Cost Auditor -- an AI that analyzes the token usage and costs
of other AI agents (specifically OpenClaw/Clawdbot/Moltbot agents).

Your job is to:
1. Show users exactly where their money is going when running AI agents
2. Find HIDDEN costs that users don't know about (heartbeats, memory resyncs, tool retries, compactions)
3. Estimate costs BEFORE running tasks so users can make informed decisions
4. Recommend specific optimizations to reduce spending

You have access to these tools:
- get_agent_overview: Shows all agents and their total usage/costs
- find_hidden_costs: Deep analysis of wasteful token consumption patterns
- estimate_task_cost: Pre-calculate what a task will cost before running it
- get_cost_timeline: Show when and where money was spent over time

Be direct, specific, and quantitative. Always show dollar amounts.
When you find waste, be bold about calling it out.
Use comparisons that make costs tangible.
Format responses with clear sections. Use bullet points sparingly.
Lead with the most impactful finding.
"""

def create_agent():
    """Create and return the Strands Agent configured with Bedrock."""
    setup_datadog_telemetry()
    model = AnthropicModel(model_id="claude-sonnet-4-20250514", max_tokens=4096)
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[get_agent_overview, find_hidden_costs, estimate_task_cost, get_cost_timeline],
        trace_attributes={
            "session.id": "hackathon-demo",
            "user.id": "ricardo@lawgic.com",
            "tags": ["hackathon", "agent-cost-auditor", "openclaw"]
        }
    )
    return agent

# --- CLI Mode ---
if __name__ == "__main__":
    print("\nBudget Agent")
    print("=" * 50)
    print("Analyzing your AI agent costs...\n")
    print("Type a question or 'q' to quit\n")
    agent = create_agent()
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                break
            if not user_input:
                continue
            print("\nAuditor: ", end="", flush=True)
            result = agent(user_input)
            print()
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
