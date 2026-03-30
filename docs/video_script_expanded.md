# SentinelStream AI — 3-Minute Demo Video Script

**Title:** SentinelStream AI: Autonomous DevOps Governance for GitLab Duo
**Length:** ~3:00

## Scene 1: The Conflict (0:00 - 0:45)

**Visuals:**
- Start with a screen recording of the GitLab Web IDE or a local editor.
- The developer opens `package.json` in a new feature branch (`feat/add-pdf-export`).
- They add a new dependency: `"itextpdf": "^5.5.13"`.
    - *(Narrator notes: This is a well-known AGPL licensed library, which violates typical corporate policies).*
- The developer also adds `"express": "^3.1.0"`.
    - *(Narrator notes: An ancient version of Express with known critical CVEs).*
- The developer commits the code and opens a Merge Request.
- Switch to the GitLab MR view showing the open MR with the changes.

**Narration / Voiceover:**
> "Modern development moves fast. So fast, that security and compliance often become bottlenecks. Look at this typical scenario: a developer adds a couple of libraries to parse PDFs and spin up a quick server route. They don't know that one library carries an AGPL license, and the other is an outdated version with a critical CVE. In a standard workflow, this would sit in an MR queue until a security review flags it days later, forcing a rewrite."

---

## Scene 2: The Agent at Work (0:45 - 2:00)

**Visuals:**
- Split-screen effect.
- **Left side:** The GitLab MR page. A small, spinning "SentinelStream AI" badge appears in the pipeline/MR checks area.
- **Right side:** A simulated terminal window tailing the backend server logs showing the actual Python backend "thinking".

**Log text (scrolling fast):**
```text
[INFO] Received MR event: !42 (update) by dev-user on feat/add-pdf-export
[INFO] **Step A (Scout):** Scanning MR diff for dependency changes...
[INFO] File package.json: 2 new dependencies -> deltas: itextpdf (NEW), express (NEW)
[INFO] **Step B (Analyze):** Checking licenses and vulnerabilities...
[INFO] Lawyer verdict: itextpdf@5.5.13 → license=AGPL-3.0, vulns=0, action=block
[INFO] Lawyer verdict: express@3.1.0 → license=MIT, vulns=5, action=block
[INFO] **Step C (Remediate):** 2 dependency(ies) need remediation...
[INFO] Fixer: express@3.1.0 → Upgrade to 4.19.2 (verified=True)
[INFO] Fixer: itextpdf@5.5.13 → No compliant version found automatically
[INFO] **Step D (Self-Verify):** All proposed fixes re-checked for compliance.
```

**Narration / Voiceover:**
> "But with SentinelStream AI, our custom agent on the GitLab Duo platform wakes up instantly. Using a Plan-and-Execute DAG Architecture, it acts as a digital security teammate. Let's look at its internal monologue. First, the 'Scout' agent identifies exactly what changed. Then, our 'Lawyer' agent checks the corporate policy and queries the Google Cloud OSV database. Finally, the 'Fixer' agent kicks in. It realizes Express has vulnerabilities and searches for a compliant upgrade. Because SentinelStream knows it can't just suggest a random fix, it actively self-verifies the new version against the policy before proposing it."

---

## Scene 3: The Resolution (2:00 - 3:00)

**Visuals:**
- The split-screen ends. We return fully to the GitLab MR view.
- A new comment drops in automatically from `@sentinelstream-bot`.
- The user clicks the native GitLab "**Apply suggestion**" button on the Express version fix to instantly commit the upgrade.
- The user expands the `<details>` section for `itextpdf` showing the AGPL blocker and the reasoning log.

**Narration / Voiceover:**
> "Within seconds, SentinelStream posts a comprehensive audit report directly to the Merge Request. It provides a visual breakdown of compliance status. For the vulnerable Express package, SentinelStream hasn't just flagged the issue—it has provided the exact code snippet to fix it securely. With one click on GitLab's native 'Apply Suggestion' button, the fix is merged. For the AGPL violation, the agent provides a detailed reasoning chain, explaining exactly why the package was blocked, empowering the developer to make an informed alternative choice without waiting for a manual security review.
>
> SentinelStream AI: Turning security bottlenecks into developer velocity."
