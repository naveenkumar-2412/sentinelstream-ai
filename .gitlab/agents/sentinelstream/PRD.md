# HACKATHON PROJECT DOCUMENTATION: SENTINELSTREAM AI

**Project:** GitLab AI Hackathon 2026  
**Category:** Productivity / Machine Learning & AI / Security  
**Status:** Draft Product Requirements Document (PRD) & Design Guide

---

## 1. EXECUTIVE SUMMARY

SentinelStream AI is an autonomous governance agent built on the GitLab Duo Agent Platform. Unlike traditional "scan-and-flag" security tools, SentinelStream acts as a digital teammate that triggers on Merge Requests (MRs). It identifies dependency risks, reasons through license compatibility, and proactively generates remediation commits to keep the software development lifecycle (SDLC) moving without manual security bottlenecks.

---

## 2. PRODUCT REQUIREMENTS DOCUMENT (PRD)

### 2.1 Problem Statement

Security and compliance reviews are the "silent killers" of developer velocity. Developers often add libraries that:

- Contain critical vulnerabilities (CVEs).
- Have restrictive licenses (GPL/AGPL) that conflict with corporate policy.
- Are outdated or unmaintained.

Current tools only alert the developer; they don't fix the problem, leading to "alert fatigue" and delayed deployments.

### 2.2 The Solution

SentinelStream is an autonomous agent that:

1. **Triggers automatically** when a dependency file is modified.
2. **Researches** the vulnerability and license status using external APIs (Google Cloud OSV).
3. **Decides** on the best course of action (Upgrade vs. Alternative).
4. **Executes** the fix by creating a sub-branch and a "Remediation MR."

### 2.3 User Stories

| ID | As a... | I want to... | So that... |
|----|---------|-------------|-----------|
| US1 | Developer | Push code without worrying about license conflicts | I can focus on feature development |
| US2 | Security Lead | Have an automated audit trail of every dependency decision | I can satisfy SOC2/ISO27001 audits |
| US3 | Engineering Manager | Reduce MR cycle time caused by compliance reviews | My team ships faster |

### 2.4 Functional Requirements

| ID | Requirement |
|----|------------|
| FR1 | Integration with GitLab Duo Agent Platform |
| FR2 | Automated parsing of `package.json`, `requirements.txt`, and `go.mod` |
| FR3 | Multi-Agent Orchestration (Scout Agent, Legal Agent, Fixer Agent) |
| FR4 | Asynchronous reporting via MR comments |

---

## 3. TECHNICAL ARCHITECTURE

### 3.1 Tech Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | GitLab Duo Agent Platform / GitLab Flows |
| Models | Anthropic Claude-3 (via GitLab) for reasoning; Gemini 1.5 Flash (via Google Cloud) for fast data parsing |
| Backend | Python (FastAPI) hosted on Google Cloud Run |
| Database | Google Cloud SQL (PostgreSQL) for policy storage |

### 3.2 Agent Workflow Logic

1. **MR Event Hook:** GitLab sends a webhook to the SentinelStream backend.
2. **Analysis Phase:** Agent-Scout identifies the "Delta" (the exact libraries changed).
3. **Policy Check:** Agent-Lawyer reads the local `POLICY.md` and compares it with the library metadata.
4. **Remediation Phase:** If a conflict exists, Agent-Fixer uses Google Search (via GitLab Duo) to find the nearest stable, compliant version and submits a suggested change.

---

## 4. DESIGN & VISUAL IDENTITY

To ensure the agent feels like a native part of the GitLab ecosystem, the following design tokens are used:

### 4.1 Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--sentinel-green` | `#108548` | Compliant / Pass states |
| `--sentinel-amber` | `#E5A00D` | Warnings / Advisory |
| `--sentinel-red` | `#DD2B0E` | Blockers / Critical CVEs |
| `--sentinel-blue` | `#1F75CB` | Informational links |

### 4.2 UI Components

- **The "Sentinel Badge":** A dynamic SVG icon displayed in the MR description indicating the "Governance Score."
- **Logic Disclosure:** A collapsed Markdown section in MR comments labeled "Show SentinelStream's Reasoning" to build trust with developers.

---

## 5. SUBMISSION & IMPACT STRATEGY

### 5.1 Scoring Objectives

| Prize Category | How We Win |
|---------------|-----------|
| Most Technically Impressive | Multi-agent orchestration rather than a single prompt |
| Most Impactful | Solves the "compliance bottleneck," a multi-billion dollar friction point |
| Green Agent Prize | Token optimization via Scout/Reasoning model routing |

### 5.2 Demo Video Script (3 Minutes)

| Timestamp | Scene |
|-----------|-------|
| 0:00–0:45 | **The Conflict.** A developer unknowingly adds a library with an AGPL license. |
| 0:45–2:00 | **The Agent at Work.** Split screen showing the Agent "thinking" and searching for an MIT-licensed alternative. |
| 2:00–3:00 | **The Resolution.** The Agent posts a comment with a fix and a "Quick Action" to apply it. |
