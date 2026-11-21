---
name: obsi-inspect
kind: workflow
uses:
  - second-brain
description: "[Workflow] Layer 4 Chief Auditor & In-Flight Chat Inspector (`/obsi-inspect`): extracts transcript delta steps, audits consultant claims & sycophancy, verifies facts, and runs deterministic Vault health checks. Silent in normal chat."
---

# `obsi-inspect` — Layer 4 Chief Auditor & In-Flight Inspector

Active **ONLY** on **`/obsi-inspect`** (or explicit audit requests). Remains completely silent in normal engineering chat.

## 1. In-Flight Chat Delta Inspection (`/obsi-inspect`)
1. Identify the current `conversation_id` and run [extract_session_steps.py](../second-brain/scripts/extract_session_steps.py):
   - Auto-delta from previous inspect/consult marker:
     `python "<second-brain-dir>/scripts/extract_session_steps.py" --chat-id <id> --since-last-inspect`
   - Or inspect marker anchors (`--find-markers`) and pass `--start <S> --end <E>`.
2. Audit the extracted delta strictly (`governance_and_audit.md` §6):
   - **Evidence Check:** Did consultant claims cite real playbooks/URLs/Vault docs (`Verified`) or sneak in unverified guesses?
   - **Anti-Sycophancy & User Calibration:** Did the consultant flatter blindly OR fail to calibrate when the founder shared domain knowledge?
   - **Live Fact Check:** Run targeted `search_web` or file read for any disputed claim/number.
3. Emit a crisp 3-part card (in the user's language):
   - **Verified:** Evidence-backed findings.
   - **Drift / Unverified:** Ungrounded claims or skipped gates.
   - **Verdict / Next Step:** Specific correction or probe.
4. Sync under `## Inspector Audit` in `00-Focus/Scorecards/<Project>.md` or `00-Focus/Decisions/YYYY-MM-DD - <Slug>.md` upon confirmation/close.

## 2. Deterministic Vault & Skills Audit (`/obsi-inspect vault`)
Run [vault_audit.py](../second-brain/scripts/vault_audit.py) (`--json` optional) and report `Verified`, `Warnings / Needs Review`, and `Errors` concisely.
