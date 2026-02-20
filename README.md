# 🔍 Agent Cost Auditor

**The AI agent that audits your AI agents.** Built with Strands Agents + Amazon Bedrock + Datadog LLM Observability.

Analyzes OpenClaw/Clawdbot token usage to find hidden costs (heartbeats, memory resyncs, tool retries) and recommends optimizations.

## Quick Start (Hackathon)

```bash
# 1. Clone and setup
cd agent-cost-auditor
cp .env.example .env
# Edit .env with your real credentials

# 2. Install dependencies
cd backend
pip install -r requirements.txt

# 3. Set environment variables
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_DEFAULT_REGION="us-west-2"
export DD_API_KEY="your_datadog_api_key"
export DD_SITE="us5.datadoghq.com"

# 4. Run the server
python server.py
# Open http://localhost:8080
```

## Architecture

```
┌──────────────────┐     ┌─────────────────────┐
│  OpenClaw Logs   │────▶│  Agent Cost Auditor  │
│  sessions.json   │     │  (Strands + Bedrock) │
│  *.jsonl files   │     └──────────┬──────────┘
└──────────────────┘                │
                          ┌─────────▼─────────┐
                          │  Datadog LLM Obs   │
                          │  (OTEL Traces)     │
                          └─────────┬─────────┘
                          ┌─────────▼─────────┐
                          │   Web Dashboard    │
                          │   + Chat Agent     │
                          └───────────────────┘
```

## Features

- **Hidden Cost Detection**: Finds heartbeats, memory resyncs, tool retries, compactions
- **Pre-Execution Estimation**: Estimates cost before running a task
- **Agent Comparison**: Shows which agents waste the most
- **Optimization Recommendations**: Specific fixes with savings percentages
- **Interactive Chat**: Ask the auditor anything about your spending
- **Datadog Integration**: Full LLM Observability traces

## Stack

- **Strands Agents SDK** — Agent orchestration
- **Amazon Bedrock** — Claude Sonnet 4 as the reasoning model
- **Datadog LLM Observability** — OpenTelemetry traces
- **FastAPI** — API server
- **Vanilla HTML/CSS/JS** — Zero-dependency frontend

## Using Real OpenClaw Data

Copy your OpenClaw session data:

```bash
# From your OpenClaw server
scp ~/.openclaw/agents/*/sessions/sessions.json ./data/sessions.json
scp ~/.openclaw/agents/*/sessions/*.jsonl ./data/
```

## CLI Mode

```bash
cd backend
python agent.py
# Interactive chat with the auditor
```
