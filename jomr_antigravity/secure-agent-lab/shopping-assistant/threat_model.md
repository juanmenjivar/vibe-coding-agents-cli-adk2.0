# STRIDE Threat Model Assessment: Shopping Assistant

This document presents a systematic security assessment of the `shopping-assistant` agent using the STRIDE threat modeling methodology.

## System Boundaries & Data Flows
- **Entry Points**:
  - User text inputs received by `root_agent` (defined in `app/agent.py`).
  - Model invocations made via `Gemini` with a custom client.
- **Privileged Actions**:
  - `redeem_discount_code` tool calls (defined in `app/tools.py`).
  - Command execution tools (governed by the `PreToolUse` hook intercept).
- **Data Stores**:
  - Transient in-memory dictionary `DISCOUNT_CODES` and set `REGISTERED_USERS` within `app/tools.py`.

---

## STRIDE Threat Evaluation

### 1. Spoofing (Identity Spoofing)
- **Threat**: The `redeem_discount_code` tool accepts `user_id` as an unverified string argument. A malicious user could input another registered user's ID (e.g., `user_2` claiming to be `user_1`) and redeem single-use codes on their behalf.
- **Risk Severity**: **HIGH**
- **Mitigation**: Bind the `user_id` securely to the authenticated session context (e.g., resolving the current session's authenticated caller ID via `ToolContext` state rather than prompting the user for a raw ID parameter).

### 2. Tampering (Data Tampering)
- **Threat**: The discount code status is kept in an in-memory dictionary (`DISCOUNT_CODES`). Concurrent requests could exploit race conditions (time-of-check to time-of-use / TOCTOU) to redeem a single-use code multiple times before state updates.
- **Risk Severity**: **MEDIUM**
- **Mitigation**: Move from a simple in-memory dictionary to a transactional database (e.g., PostgreSQL or SQLite) utilizing atomic transactions or lock checks during discount application.

### 3. Repudiation (Repudiation of Actions)
- **Threat**: Redemptions and access validations are logged transitively to standard outputs but not persisted to a tamper-proof audit trail. Users could deny redeeming a code, and admins would have no immutable records to audit.
- **Risk Severity**: **LOW**
- **Mitigation**: Implement persistent logging of successful/failed redemptions to an external logging system (e.g., Cloud Logging) with restricted modification access.

### 4. Information Disclosure (Information Leakage)
- **Threat**: The model client in `app/agent.py` is initialized with a simulated hardcoded API key (`api_key="AIzaSyD-mock-key-value-12345"`). While mock, keeping real credentials in code leads to severe API key exposure.
- **Risk Severity**: **HIGH** (in production environments)
- **Mitigation**: Enforce the use of environment variables (`os.environ`) or Google Cloud Secret Manager to resolve sensitive API keys. Use Semgrep checks in CI/CD to prevent commits containing `AIzaSy` prefixes.

### 5. Denial of Service (DoS)
- **Threat**: The application lacks rate limits on user queries. Malicious actors could flood the shopping assistant with inputs, exhausting the Gemini API quota and incurring significant costs.
- **Risk Severity**: **MEDIUM**
- **Mitigation**: Implement request rate-limiting at the API gateway layer or within the FastAPI application middleware, restricting requests per user/IP.

### 6. Elevation of Privilege (Privilege Escalation)
- **Threat**: If `run_command` or terminal capabilities are exposed to the agent, a compromised agent could escape constraints. While `hooks.json` uses a `PreToolUse` validator script to block destructive commands like `rm -rf /`, execution of arbitrary commands might still be possible if validation logic contains bypasses.
- **Risk Severity**: **CRITICAL**
- **Mitigation**: Adhere to the *principle of least privilege*. Do not register or expose the `run_command` tool in the agent configuration at all. Rely only on narrow, typed domain tools.

---

## Actionable Security Recommendations
1. **Remove Hardcoded Key**: Refactor `app/agent.py` to fetch the API key from environment variables before deploying to production.
2. **Context-Driven Auth**: Retrieve `user_id` directly from authenticated session claims rather than accepting it as an user-supplied parameter in the tool.
3. **Transition to Persistent Storage**: Replace the in-memory dictionaries with a transactional database to guarantee ACID compliance for code redemptions.
