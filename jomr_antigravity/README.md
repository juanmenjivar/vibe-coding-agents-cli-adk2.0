# jomr_antigravity Workspace

Welcome to the **jomr_antigravity** developer workspace. This repository acts as a monorepo for several experimental and production AI agents built using the Google Agent Development Kit (ADK) and custom orchestrations.

---

## 📂 Repository Layout

The workspace is organized as follows:

```
jomr_antigravity/
├── .agents/                      # Workspace Customizations & Development Rules
│   └── skills/                   # Local ADK custom skills
│       ├── database-schema-validator # Safety checks for SQL schemas
│       ├── git-commit-formatter      # Standardizes Conventional Commits messages
│       ├── json-to-pydantic          # Converts raw JSON payloads to Pydantic classes
│       └── license-header-adder      # Automates open-source license injection
├── ambient-expense-agent/        # Stateful event-driven ambient expense compliance agent (FastAPI, Port 8080)
├── customer_support_agent/       # Support agent for helpdesk ticketing, order lookups, and FAQ routing
├── secure-agent-lab/             # Local workspace lab containing git identity and virtual environment setup
├── weather-assistant/            # Conversational bot for open-meteo weather queries and itinerary tracking
├── agy-cli-projects/             # Scratch CLI test configurations and drafts
├── bad_schema.sql                # SQL schema example used for testing the schema safety policy validator
├── demo_bad_code.py              # Script fixture for testing linter/compliance rules
├── product_model.py              # Pydantic data model definitions
└── README.md                     # This file
```

---

## 🚀 Projects Overview

### 1. [ambient-expense-agent](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/ambient-expense-agent)
An event-driven ambient service that processes corporate expenses via Pub/Sub trigger messages:
- **Stateful Graph Core**: Evaluates submitter information, category, amount, and description.
- **Security Checkpoints**: Automatically redacts sensitive PII (Social Security Numbers) and detects prompt-injection attacks (e.g. bypass rules, model bypass) to route directly to human reviewers.
- **Auto-Approval**: Under $100 expenses are automatically approved. $100 or more goes to a human-in-the-loop (HITL) manual approval.
- **Local Quality Flywheel**: Includes a trace generator script to automate HITL decisions and a suite of custom LLM-as-judge metrics (`routing_correctness`, `security_containment`) for scoring agent traces.

### 2. [customer_support_agent](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/customer_support_agent)
An interactive customer support assistant built to streamline customer helpdesk workflows:
- Connects to CRM and database mock services to retrieve order details, track shipments, and resolve common customer disputes.
- Routes complex queries to human operators or departments using conditional graph logic.

### 3. [secure-agent-lab](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/secure-agent-lab)
A sandbox lab workspace hosting the `shopping-assistant` agent, used to implement and test the secure agentic coding practices from the [Google Developers Codelab](https://codelabs.developers.google.com/secure-agentic-coding):
- **Mock-based TDD Security Tests**: Enforces security boundaries and business logic guardrails (e.g. registered user requirements, single-use discounts, cart double-checkout checks) in [tests/test_agent_security.py](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/secure-agent-lab/shopping-assistant/tests/test_agent_security.py).
- **STRIDE Threat Model**: Includes architectural threat assessment in [threat_model.md](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/secure-agent-lab/shopping-assistant/threat_model.md).
- **Pre-Commit Remediation Loop**: Detects and refactors hardcoded secrets autonomously.
- **Pre-Tool Interceptors**: Features `PreToolUse` interceptors in [.agents/hooks.json](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/secure-agent-lab/shopping-assistant/.agents/hooks.json) blocking destructive command execution.

### 4. [weather-assistant](file:///c:/Users/JUANM/Downloads/cursor_jomr_projects/jomr_antigravity/weather-assistant)
A conversational weather assistant powered by ADK:
- Connects to geocoding and weather API tools (e.g., Open-Meteo) to fetch real-time forecasts, temperatures, and wind conditions.
- Helps plan itineraries by offering weather advice based on dates and locations.

---

## 🛠️ Workspace Guidelines & Practices

### Git Commit Conventions
All commit messages in this workspace **must** adhere to the **Conventional Commits** specification. The workspace custom skill `git-commit-formatter` provides local enforcement:
- **Format**: `<type>[optional scope]: <description>` (e.g. `feat(expense): add PII redaction node`, `fix(eval): resolve traceback on empty candidate`).
- **Allowed Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`.

### Coding Standards
- **License Headers**: New source code files should include appropriate copyright license headers, which can be formatted using the `license-header-adder` skill.
- **Pydantic Schemas**: When processing JSON API inputs or outputs, define strict Pydantic structures. Use `json-to-pydantic` to speed up schema conversion.
- **Database Safety**: SQL schema definition files (like `bad_schema.sql`) must be checked for safety, naming conventions, and compliance rules using the `database-schema-validator` skill.
