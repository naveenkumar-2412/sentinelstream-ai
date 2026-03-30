# SentinelStream — Repository Compliance Policy

> This file defines the dependency governance rules for this repository.
> If this file is missing, SentinelStream defaults to **Zero Trust** mode
> (block everything except MIT and Apache-2.0).

---

## 1. Allowed Licenses

Only dependencies with the following SPDX license identifiers are permitted:

| SPDX Identifier | Status |
|-----------------|--------|
| `MIT` | ✅ Allowed |
| `Apache-2.0` | ✅ Allowed |
| `BSD-2-Clause` | ✅ Allowed |
| `BSD-3-Clause` | ✅ Allowed |
| `ISC` | ✅ Allowed |
| `0BSD` | ✅ Allowed |

## 2. Blocked Licenses

Dependencies with these licenses are **always blocked** and will trigger a remediation MR:

| SPDX Identifier | Reason |
|-----------------|--------|
| `GPL-2.0-only` | Copyleft — incompatible with proprietary distribution |
| `GPL-3.0-only` | Copyleft — incompatible with proprietary distribution |
| `AGPL-3.0-only` | Network copyleft — triggers on SaaS usage |
| `LGPL-2.1-only` | Weak copyleft — requires review |
| `SSPL-1.0` | Server-side restriction |
| `EUPL-1.2` | Copyleft with jurisdictional clauses |

## 3. CVE Severity Thresholds

| Severity | CVSS Range | Action |
|----------|-----------|--------|
| Critical | 9.0–10.0 | 🔴 **Block MR** — auto-generate remediation |
| High | 7.0–8.9 | 🟠 **Warn** — post advisory comment, suggest upgrade |
| Medium | 4.0–6.9 | 🟡 **Info** — log in audit trail only |
| Low | 0.1–3.9 | ⚪ **Pass** — no action |

## 4. Exceptions

List any packages that are explicitly exempted from policy checks:

```yaml
exceptions:
  # - package: "example-lib"
  #   reason: "Approved by legal on 2026-01-15"
  #   approved_by: "security-team"
```

## 5. Policy Version

| Field | Value |
|-------|-------|
| Version | `1.0.0` |
| Last Updated | `2026-03-30` |
| Maintainer | `@security-team` |
