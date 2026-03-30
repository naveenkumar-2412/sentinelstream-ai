# 🛡️ SentinelStream AI

**Autonomous DevOps Governance Agent for GitLab**

> *GitLab AI Hackathon 2026 — Productivity / ML & AI / Security*

SentinelStream AI is an autonomous governance agent built on the GitLab Duo Agent Platform. It monitors Merge Requests for dependency risks (CVEs + license conflicts) and proactively generates remediation commits.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    GitLab MR Webhook                     │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│              FastAPI Backend (/webhook)                   │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Agent-Scout  │→│ Agent-Lawyer  │→│ Agent-Fixer   │   │
│  │ (Delta)      │  │ (Compliance) │  │ (Remediation)│   │
│  └─────────────┘  └──────────────┘  └──────────────┘   │
│         │                │                 │             │
│         ▼                ▼                 ▼             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Dep Parser   │  │ OSV Client   │  │ License      │   │
│  │ (json/txt/   │  │ (CVE DB)     │  │ Checker      │   │
│  │  go.mod)     │  │              │  │ (PyPI/npm/Go)│   │
│  └─────────────┘  └──────────────┘  └──────────────┘   │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │           Logic Gating (Model Router)              │  │
│  │   Patch → Gemini Flash │ Major/New → Claude-3      │  │
│  └───────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│          GitLab API (Comments, Suggestions, MRs)         │
└──────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Set Environment Variables

```bash
export SENTINEL_GITLAB_TOKEN="glpat-xxxxxxxxxxxx"
export SENTINEL_GITLAB_URL="https://gitlab.com"
export SENTINEL_GITLAB_WEBHOOK_SECRET="your-webhook-secret"
export SENTINEL_GEMINI_API_KEY="your-gemini-key"       # Optional
export SENTINEL_CLAUDE_API_KEY="your-claude-key"       # Optional
```

### 2. Install & Run Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### 3. Deploy to Cloud Run

```bash
gcloud builds submit --config cloudbuild.yaml
```

### 4. Configure GitLab Webhook

In your GitLab project → **Settings → Webhooks**:
- **URL:** `https://your-cloud-run-url/webhook`
- **Secret token:** Same as `SENTINEL_GITLAB_WEBHOOK_SECRET`
- **Trigger:** ✅ Merge request events

---

## Project Structure

```
.gitlab/agents/sentinelstream/
├── PRD.md                  # Product Requirements Document
├── POLICY.md               # License & CVE compliance policy
└── agent_prompt.md         # Master orchestrator system prompt

backend/
├── main.py                 # FastAPI app + webhook endpoint
├── config.py               # Environment-driven settings
├── requirements.txt        # Python dependencies
├── Dockerfile              # Cloud Run container
├── agents/
│   ├── orchestrator.py     # Plan-and-Execute DAG controller
│   ├── scout.py            # Dependency delta detection
│   ├── lawyer.py           # License + CVE compliance
│   └── fixer.py            # Remediation generator
├── services/
│   ├── gitlab_api.py       # GitLab REST API bridge
│   ├── osv_client.py       # Google Cloud OSV client
│   └── license_checker.py  # Multi-registry license lookup
├── parsers/
│   └── dependency_parser.py # requirements.txt/package.json/go.mod
├── models/
│   └── schemas.py          # Pydantic data models
└── templates/
    └── comment_template.py # GitLab Markdown formatter

cloudbuild.yaml             # GCP Cloud Build config
```

---

## How It Works

1. **Developer pushes code** that modifies `requirements.txt`, `package.json`, or `go.mod`
2. **GitLab sends webhook** to SentinelStream's `/webhook` endpoint
3. **Agent-Scout** parses the MR diff and identifies dependency deltas
4. **Agent-Lawyer** checks each dependency's license (via PyPI/npm/Go) and CVEs (via OSV)
5. **Agent-Fixer** finds compliant upgrade versions and self-verifies them
6. **Comment posted** on the MR with summary table, reasoning disclosure, and quick-action commands

### Logic Gating (Green Agent Prize)

| Change Type | Model Used | Rationale |
|------------|-----------|-----------|
| Patch bump (1.0.1→1.0.2) | Gemini 1.5 Flash | Fast, low-cost verification |
| Minor bump (1.0→1.1) | Gemini 1.5 Flash (extended) | Moderate analysis |
| Major bump or new library | Anthropic Claude-3 | Deep reasoning required |

---

## License

MIT
