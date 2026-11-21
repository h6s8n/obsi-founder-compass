# 🧭 Obsi Founder Compass

**English** | [فارسی](README.fa.md)

[![CI](https://github.com/h6s8n/obsi-founder-compass/actions/workflows/ci.yml/badge.svg)](https://github.com/h6s8n/obsi-founder-compass/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **Your Antigravity agent turns messy founder ideas and multi-project chaos into one clear path — inside Native Obsidian Bases, zero third-party plugins, 100% local Markdown + Git.**

Building two or three startups while shipping features every night, only to wake up with scattered notes, stale tasks, and AI chats that drift back into CSS tweaks instead of finding your first paying buyers? **Obsi Founder Compass** gives you a 5-layer Hub-and-Spoke compass: from raw vision and market gaps down to time-boxed validation cohorts, daily unlocked tasks, and an in-flight chat auditor — while staying completely silent during normal coding.

---

## 🗺️ How it flows

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/architecture-en-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/architecture-en-light.svg">
  <img alt="Obsi Founder Compass flow: /obsi hub -> L0 setup, L1 consult, L2 priority, L4 inspect -> Vault, Strategy Cache &amp; Truth Engine" src="docs/assets/architecture-en-dark.svg" width="680">
</picture>
</p>

---

## 🚀 Install in 3 commands

```bash
git clone https://github.com/h6s8n/obsi-founder-compass.git && cd obsi-founder-compass

# 1. Install the plugin into Antigravity
agy plugin install .

# 2. Reload Antigravity IDE, open any project workspace, and type:
#    /obsi
```

That's it. If you don't have a Vault yet, a 4-question interactive wizard sets everything up cleanly after showing you a dry-run preview.

---

## 💬 How does it work? (plain words)

**How do I organize multiple projects without drowning in Obsidian plugins?**
Run `/obsi-setup` (or type `/obsi` on first launch). Four quick clickable questions build a clean Git-tracked Vault powered 100% by **Native Obsidian Bases** (`.base` kanbans + inline project boards) with your calendar choice (`en` Mon–Sun or `fa` Sat–Fri) — zero community plugins needed.

**How does `/obsi-consult` stop AI from drifting into code reviews?**
Every project gets a **Vision Mirror Gate** (4 plain lines confirmed by you first) and a strict **No-Code Firewall**: strategy sessions look purely at buyers, competitors, pricing, supply, and trust — never source code or server configs. Verified market findings are cached in `playbooks/` (`90-day` TTL) so the agent never wastes searches repeating the same research.

**Will it lecture me about working on too many projects?**
No. **Layer 1** (`/obsi-consult`) evaluates each startup strictly on its own market merits (**No Capacity Policing**). Only when you step into **Layer 2** (`/obsi-priority`) do you get optional Light/Medium/Deep pacing proposals alongside concrete 14-day **Cohorts** (`Scale / Pivot / Kill` gates). You always decide what runs.

**What do I actually type every day?**
Just `/obsi`. It auto-detects which workspace folder you're sitting in and pops up a clickable menu across all 5 layers — or jump straight to daily execution with `/obsi next` (top unblocked task) and `/obsi done` (marks complete and unlocks any dependent `Locked` card).

**How do I catch AI hallucinations or blind agreement?**
Run `/obsi-inspect` mid-conversation. It reads only the new chat turns since your last inspection (`transcript.jsonl`), cross-checks cited URLs and numbers, flags any unverified guesses, and runs a 1-second deterministic Vault audit (`vault_audit.py`).

**Does it interrupt my regular coding sessions or send my notes anywhere?**
No. Consultation and audit rules stay completely dormant until you type an `/obsi*` command. Every task, scorecard, decision log, and playbook stays on your own machine as plain Markdown under Git.

---

## 📚 Go deeper

- 🧠 **[How the 5-layer system works](docs/how-it-works.md)** — Native Bases schema, No-Code Firewall, Playbook Cache, Scorecards, and auto-unlocks.
- 🧭 **[Commands, CLI scripts & config](docs/commands.md)** — `/obsi`, `/obsi-setup`, `/obsi-consult`, `/obsi-priority`, `/obsi-inspect`, and `brain-os.json`.
- 🧪 **[Testing & zero-leakage checks](docs/verification.md)** — Automated E2E test suite, deterministic Vault auditor, and `agy plugin validate`.

---

<a id="donate"></a>

## ☕ Buy Me a Coffee (On-Chain Support)

[![Live On-Chain Donations](https://raw.githubusercontent.com/h6s8n/antigravity-skill-compass/badges/donation_badge.svg)](https://tronscan.org/#/address/TZ6CDh5UXKKgq8CQbHW6VDxY3fnzQAABbo)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/h6s8n/antigravity-skill-compass/badges/donation_meter_dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/h6s8n/antigravity-skill-compass/badges/donation_meter_light.svg">
  <img alt="Live On-Chain Wallet Gauge (Empty vs Filled + 50% Cancer Care Split)" src="https://raw.githubusercontent.com/h6s8n/antigravity-skill-compass/badges/donation_meter_dark.svg" width="100%">
</picture>

If this 5-layer Obsidian Vault architecture, the No-Code Strategy Firewall, or the in-flight transcript inspector helped you stop context-switching and ship real traction faster:

- ⭐ **Star this repository** to help fellow indie founders and vibe-coders find plugin-free workflows.
- 🤝 **Contribute:** PRs adding anonymized industry Playbooks, localized calendar/template packs, or CI verification checks are warmly welcomed under the [MIT License](LICENSE).
- ☕ **Buy me a coffee (Direct On-Chain Transfers):**
  Support the project instantly with low-fee direct transfers to the shared watch-only addresses below (verified live on-chain on the tracker gauge above):

| Network / Accepted Assets | Public Wallet Address | Explorer |
| :--- | :--- | :--- |
| **TRON (`USDT TRC20`, `TRX`)** | `TZ6CDh5UXKKgq8CQbHW6VDxY3fnzQAABbo` | [View on Tronscan](https://tronscan.org/#/address/TZ6CDh5UXKKgq8CQbHW6VDxY3fnzQAABbo) |
| **EVM (`USDC`, `USDT`, `ETH` — Base / Arbitrum / Ethereum)** | `0x0a4C4D067526AcFDb394469D1227754211b90c49` | [Basescan](https://basescan.org/address/0x0a4C4D067526AcFDb394469D1227754211b90c49) · [Etherscan](https://etherscan.io/address/0x0a4C4D067526AcFDb394469D1227754211b90c49) |

> **🎗️ 50% Charity Pledge:** **50% of all received donations** will be donated to support **cancer patients**. Because every deposit lands on public on-chain addresses, the total amount raised and its 50% charity allocation remain openly verifiable at any time.
