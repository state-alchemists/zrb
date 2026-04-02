---
name: review
description: Rigorous code review covering functional correctness, security (OWASP Top 10 checklist), performance, and maintainability. Use after any code changes, or when asked to audit code quality or find vulnerabilities.
user-invocable: true
---
# Skill: review

When this skill is activated, you enter **Auditor Mode**. Critically evaluate the code for correctness, security, and quality. Do not modify code during review — produce findings and let the user decide what to fix.

For large diffs that would consume significant context, delegate to the `code-reviewer` agent instead: `DelegateToAgent('code-reviewer', 'Review the recent changes', '<context>')`.

---

## Step 1 — Scope Identification

- Run `git status` and `git diff HEAD` to identify changed files.
- Use `ReadMany` to read changed files alongside their dependencies and tests.
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
- [ ] Path traversal possible? (e.g., `../../../etc/passwd`)

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

**A07 — Authentication Failures**
- [ ] Session tokens cryptographically random?
- [ ] Session tokens invalidated on logout?
- [ ] Secrets ever logged or included in error messages?

**A08 — Integrity Failures**
- [ ] Deserialization on untrusted data? (`pickle.loads`, `yaml.load` without `Loader`)
- [ ] User-supplied data used to construct file paths or load modules dynamically?

**A10 — SSRF**
- [ ] Any URL fetched from user input? Validated against an allowlist?

**Secrets scan**: Use `Grep` for patterns: `password\s*=`, `api_key\s*=`, `secret\s*=`, `-----BEGIN`.

---

## Step 4 — Code Quality

- Readability and naming clarity.
- Adherence to project patterns (check `CLAUDE.md`, `AGENTS.md`).
- Unreasonably high cyclomatic complexity?
- Duplication that should be extracted?
- Tests isolated — no shared mutable state between test cases?

---

## Step 5 — Verification

Run the test suite with `Bash`. A review is incomplete without knowing tests pass.

---

## Output Format

- **Summary**: Files reviewed, overall risk level.
- **Strengths**: What the author did well — balanced reviews are more actionable.
- **Findings**: Each issue with severity, `file_path:line_number`, description, and remediation.
- **Verdict**: `PASS` (no HIGH/CRITICAL) or `FAIL` (one or more HIGH/CRITICAL).

**Severity**: CRITICAL → HIGH → MEDIUM → LOW → INFO
