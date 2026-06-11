# Code Review Methodology

Do not modify code during review — produce findings and let the user decide what to fix.

For large diffs (more than 10 changed files or more than 500 total changed lines), delegate to the `code-reviewer` agent instead — if you have the `DelegateToAgent` tool. Example: `DelegateToAgent(agent_name='code-reviewer', deliverable='A severity-rated review of the recent changes with a verdict', task='Review the diff of <base>..<head>', non_goals=['do not modify code'])`. Sub-agents have no delegate tools — if you are one, review inline regardless of diff size.

---

## Step 1 — Scope Identification

- Run `git status` and `git diff HEAD` to identify changed files.
- Issue parallel `Read` calls to load changed files alongside their dependencies and tests.
- Use `LspGetDiagnostics` on changed files to surface type errors the author may have missed.

---

## Step 2 — Correctness Review

- Does the code solve the stated problem?
- Are edge cases handled? (empty input, null/None, overflow, off-by-one)
- Are error conditions propagated — or silently swallowed?
- Do the tests actually cover the new behavior?

---

## Step 3 — Security Audit (OWASP Top 10)

Work through each category for every changed file that touches user input, auth, file I/O, or external data:

**A01 — Broken Access Control**
- [ ] Authorization checks on all sensitive endpoints/functions?
- [ ] Can a user access another user's data by changing an ID?
- [ ] Path traversal possible?

**A02 — Cryptographic Failures**
- [ ] Secrets stored in plaintext?
- [ ] Passwords hashed with bcrypt/argon2 (not MD5/SHA1)?
- [ ] JWTs validated for expiry, issuer, and signature?

**A03 — Injection**
- [ ] SQL queries parameterized? No string concatenation into queries?
- [ ] User input passed to `subprocess`, `os.system`, `exec`, `eval`, or `shell=True`?
- [ ] Template inputs escaped?

**A04 — Insecure Design**
- [ ] Rate limits on authentication or sensitive endpoints?
- [ ] User enumeration possible via timing or error message differences?

**A05 — Security Misconfiguration**
- [ ] Stack traces or debug info exposed in production paths?
- [ ] CORS configured with `*` wildcard on sensitive routes?

**A06 — Vulnerable & Outdated Components**
- [ ] Are new or upgraded dependencies on known-vulnerable versions? (`npm audit`, `pip-audit`, `cargo audit`, `gh advisory`)
- [ ] Are any unmaintained packages introduced (no release in 2+ years)?
- [ ] Are version pins specific enough to prevent silent upgrades into vulnerable ranges?

**A07 — Authentication Failures**
- [ ] Session tokens cryptographically random?
- [ ] Session tokens invalidated on logout?
- [ ] Secrets ever logged or included in error messages?

**A08 — Integrity Failures**
- [ ] Deserialization on untrusted data? (`pickle.loads`, `yaml.load` without `Loader`)
- [ ] User-supplied data used to construct file paths or load modules dynamically?

**A09 — Security Logging & Monitoring Failures**
- [ ] Are auth attempts, access-control failures, and validation errors logged?
- [ ] Do logs include enough context (user, IP, action) without leaking secrets/PII?
- [ ] Are critical failures observable (alerting wired in), not just written to a file?

**A10 — SSRF**
- [ ] Any URL fetched from user input? Validated against an allowlist?

**Secrets scan**: Use `Grep` for patterns: `password\s*=`, `api_key\s*=`, `secret\s*=`, `-----BEGIN`.

> Adapt security checks to the deployment context: web/API → focus on injection, CORS, and auth; CLI/batch → focus on input validation, file permissions, and shell injection; systems/embedded → focus on resource exhaustion, integer overflow, and race conditions.

---

## Step 4 — Code Quality

- Readability and naming clarity.
- Adherence to project patterns (check `CLAUDE.md`, `AGENTS.md`).
- Unreasonably high cyclomatic complexity?
- Duplication that should be extracted?
- Tests isolated — no shared mutable state between test cases?

---

## Step 5 — Verification

Run the test suite with `Shell`. A review is incomplete without knowing tests pass.

---

## Output Format

- **Summary**: files reviewed, overall risk level.
- **Strengths**: what the author did well — balanced reviews are more actionable.
- **Findings**: each issue with severity, `file_path:line_number`, description, and remediation.
- **Verdict**: `PASS` (no HIGH/CRITICAL) or `FAIL` (one or more HIGH/CRITICAL).

**Severity**: CRITICAL → HIGH → MEDIUM → LOW → INFO
