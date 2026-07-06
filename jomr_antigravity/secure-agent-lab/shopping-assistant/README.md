# shopping-assistant

Simple ReAct agent
Agent generated with `agents-cli` version `1.0.0`

## Project Structure

```
shopping-assistant/
├── app/         # Core agent code
│   ├── agent.py               # Main agent logic
│   ├── fast_api_app.py        # FastAPI Backend server
│   └── app_utils/             # App utilities and helpers
├── tests/                     # Unit, integration, and load tests
├── GEMINI.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
```

> 💡 **Tip:** Use [Antigravity CLI](https://antigravity.google/) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)


## Quick Start

Install `agents-cli` and its skills if not already installed:

```bash
uvx google-agents-cli setup
```

Install required packages:

```bash
agents-cli install
```

Test the agent with a local web server:

```bash
agents-cli playground
```

You can also use features from the [ADK](https://adk.dev/) CLI with `uv run adk`.

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli lint`    | Run code quality checks                                                               |
| `agents-cli eval`    | Evaluate agent behavior (generate, grade, analyze, and more — see `agents-cli eval --help`) |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests                                                        || [A2A Inspector](https://github.com/a2aproject/a2a-inspector) | Launch A2A Protocol Inspector                                                        |

## 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customizations |

---

## Development

Edit your agent logic in `app/agent.py` and test with `agents-cli playground` - it auto-reloads on save.

## Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy
```

To add CI/CD and Terraform, run `agents-cli scaffold enhance`.
To set up your production infrastructure, run `agents-cli infra cicd`.

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.

## A2A Inspector

This agent supports the [A2A Protocol](https://a2a-protocol.org/). Use the [A2A Inspector](https://github.com/a2aproject/a2a-inspector) to test interoperability.
See the [A2A Inspector docs](https://github.com/a2aproject/a2a-inspector) for details.

---

## 🔒 Secure Agentic Coding & TDD Lifecycle Compliance

This project complies with the secure agentic coding guidelines outlined in the [Google Developers Codelab](https://codelabs.developers.google.com/secure-agentic-coding):

1. **STRIDE Threat Modeling**: Conducted a systematic threat assessment documented in [threat_model.md](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/secure-agent-lab/shopping-assistant/threat_model.md) to map boundaries and spoofing risks.
2. **TDD Planning Gate**: Integrated rules in [.agents/CONTEXT.md](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/secure-agent-lab/shopping-assistant/.agents/CONTEXT.md) to enforce strict boundary-condition checks on tool designs.
3. **Outcome-Based Security Tests**: Created deterministic test suites in [test_agent_security.py](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/secure-agent-lab/shopping-assistant/tests/test_agent_security.py) verifying boundaries (registered-user validation, single-use coupons, etc.).
4. **Pre-Commit Remediation Loop**: Integrated pre-commit checks to scan for credentials/secrets, ensuring safe environment variable config fallback.
5. **Tool Execution Interceptors**: Implemented a custom `PreToolUse` hook script in [.agents/hooks.json](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/secure-agent-lab/shopping-assistant/.agents/hooks.json) to intercept command executions and block destructive commands.
