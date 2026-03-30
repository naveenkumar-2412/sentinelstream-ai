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

## 3. CVE Severity Thresholds

| Severity | CVSS Range | Action |
|----------|-----------|--------|
| Critical | 9.0–10.0 | 🔴 **Block MR** — auto-generate remediation |
| High | 7.0–8.9 | 🟠 **Warn** — post advisory comment, suggest upgrade |
| Medium | 4.0–6.9 | 🟡 **Info** — log in audit trail only |
| Low | 0.1–3.9 | ⚪ **Pass** — no action |
