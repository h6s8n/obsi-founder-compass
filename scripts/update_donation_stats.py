#!/usr/bin/env python3
"""Watch-only multi-chain on-chain donation aggregator & SVG badge generator.

Reads ONLY public blockchain addresses (zero private keys) across TRON and EVM
networks, filters strictly against verified official token contracts to reject
airdrop spam, accumulates cumulative inflows, and emits a static SVG badge.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sys
import urllib.request

DEFAULT_TRON_ADDRESS = "TZ6CDh5UXKKgq8CQbHW6VDxY3fnzQAABbo"
DEFAULT_EVM_ADDRESS = "0x0a4C4D067526AcFDb394469D1227754211b90c49"

# Official verified token contracts (lowercase for EVM) — prevents spam token inflation
TRON_USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
ETH_STABLE_CONTRACTS = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6),
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6),
    "0x6b175474e89094c44da98b954eedeac495271d0f": ("DAI", 18),
}
EVM_RPC_CONFIGS = {
    "base": {
        "rpc": "https://mainnet.base.org",
        "tokens": {
            "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ("USDC", 6),
        },
    },
    "arbitrum": {
        "rpc": "https://arb1.arbitrum.io/rpc",
        "tokens": {
            "0xaf88d065e77c8cc2239327c5edb3a432268e5831": ("USDC", 6),
            "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": ("USDT", 6),
        },
    },
}
ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
MILESTONE_TIERS = (100, 250, 500, 1000, 2500, 5000, 10000)

METER_THEMES = {
    "dark": {
        "bg": "#0d1117",
        "panel": "#161b22",
        "track": "#21262d",
        "border": "#30363d",
        "text": "#f0f6fc",
        "muted": "#8b949e",
        "green": "#3fb950",
        "blue": "#58a6ff",
        "pink": "#db61a2",
        "amber": "#d29922",
        "empty_badge_bg": "#21262d",
        "empty_badge_fg": "#9ea7b3",
        "cup_outline": "#8b949e",
        "cup_empty": "#161b22",
        "split_pink_dim": "#422739",
        "split_blue_dim": "#1d2d44",
    },
    "light": {
        "bg": "#ffffff",
        "panel": "#f6f8fa",
        "track": "#eaeef2",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#57606a",
        "green": "#1a7f37",
        "blue": "#0969da",
        "pink": "#bf3989",
        "amber": "#9a6700",
        "empty_badge_bg": "#eaeef2",
        "empty_badge_fg": "#57606a",
        "cup_outline": "#57606a",
        "cup_empty": "#f6f8fa",
        "split_pink_dim": "#f6d8ea",
        "split_blue_dim": "#d8e9fc",
    },
}

METER_STRINGS = {
    "en": {
        "dir": "ltr",
        "aria": "Live Watch-Only Donation Wallet Meter",
        "title": "Watch-Only On-Chain Wallet Gauge",
        "empty_pill": "EMPTY · $0.00",
        "active_pill": "ACTIVE · ${total:,.2f}",
        "full_pill": "GOAL MET · ${total:,.2f}",
        "empty_cup": "EMPTY",
        "filled_cap": "{pct:.0f}% Full (${goal:,})",
        "milestone": "Milestone Progress: ${total:,.2f} / ${goal:,} ({pct:.1f}%)",
        "split": "50% Pledge: ${charity:,.2f} -> Cancer Care  |  ${maint:,.2f} -> Open-Source",
        "tron_lbl": "TRON (TRC20 / TRX)",
        "evm_lbl": "EVM (Base / Arb / ETH)",
        "tx_lbl": "Transactions · UTC",
    },
    "fa": {
        "dir": "rtl",
        "aria": "نمودار موجودی کیف‌پول شفاف آن‌چین",
        "title": "گیج زنده کیف‌پول دونیت (شفاف و فقط‌خواندنی)",
        "empty_pill": "خالی · \u2066$0.00\u2069",
        "active_pill": "فعال · \u2066${total:,.2f}\u2069",
        "full_pill": "هدف تکمیل · \u2066${total:,.2f}\u2069",
        "empty_cup": "خالی",
        "filled_cap": "پر شده: \u2066{pct:.0f}%\u2069 · سقف \u2066${goal:,}\u2069",
        "milestone": "پیشرفت هدف فعلی: \u2066${total:,.2f}\u2069 از \u2066${goal:,}\u2069 — \u2066{pct:.1f}%\u2069",
        "split": "تعهد ۵۰٪: \u2066${charity:,.2f}\u2069 بیماران سرطانی  |  \u2066${maint:,.2f}\u2069 توسعه",
        "tron_lbl": "شبکه TRON (TRC20)",
        "evm_lbl": "شبکه‌های EVM (Base/Arb/ETH)",
        "tx_lbl": "تراکنش‌ها · زمان UTC",
    },
}


def compute_milestone_goal(total_usd: float) -> tuple[int, float]:
    val = max(0.0, float(total_usd))
    goal = MILESTONE_TIERS[-1]
    for tier in MILESTONE_TIERS:
        if val <= tier:
            goal = tier
            break
    else:
        steps = int((val - MILESTONE_TIERS[-1]) // 5000) + 1
        goal = MILESTONE_TIERS[-1] + steps * 5000
    pct = min(100.0, round((val / goal) * 100.0, 1)) if val > 0 else 0.0
    return goal, pct


def compute_network_totals(seen_txs: dict[str, float], floor_usd: float) -> tuple[float, float, float]:
    tron_usd = sum(float(v) for k, v in seen_txs.items() if str(k).startswith("tron_"))
    evm_tx_usd = sum(float(v) for k, v in seen_txs.items() if not str(k).startswith("tron_"))
    tx_sum = tron_usd + evm_tx_usd
    extra_floor = max(0.0, float(floor_usd) - tx_sum)
    evm_usd = evm_tx_usd + extra_floor
    total_usd = round(max(tx_sum, float(floor_usd)), 2)
    return round(tron_usd, 2), round(evm_usd, 2), total_usd


def base58_decode(s: str) -> bytes:
    num = 0
    for ch in s:
        num = num * 58 + BASE58_ALPHABET.index(ch)
    combined = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    leading = len(s) - len(s.lstrip("1"))
    return (b"\x00" * leading) + combined


def tron_base58_to_hex(addr: str) -> str:
    raw = base58_decode(addr)
    if len(raw) != 25:
        raise ValueError(f"Invalid TRON address length: {len(raw)}")
    payload, chk = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != chk:
        raise ValueError("Invalid TRON Base58Check checksum")
    return payload.hex().lower()


def _http_json(url: str, body: dict | None = None, timeout: int = 15) -> dict:
    headers = {"User-Agent": "obsi-founder-compass-tracker/1.0", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_usd_prices() -> dict[str, float]:
    prices = {"trx": 0.25, "eth": 3000.0}
    try:
        res = _http_json("https://api.coingecko.com/api/v3/simple/price?ids=tron,ethereum&vs_currencies=usd")
        if isinstance(res.get("tron"), dict) and res["tron"].get("usd"):
            prices["trx"] = float(res["tron"]["usd"])
        if isinstance(res.get("ethereum"), dict) and res["ethereum"].get("usd"):
            prices["eth"] = float(res["ethereum"]["usd"])
    except Exception:
        pass
    return prices


def parse_tron_inflows(
    tron_addr: str,
    trc20_payload: dict,
    trx_payload: dict,
    trx_usd: float,
) -> dict[str, float]:
    inflows: dict[str, float] = {}
    tron_hex = tron_base58_to_hex(tron_addr)

    for tx in trc20_payload.get("data") or []:
        if not isinstance(tx, dict):
            continue
        tok = tx.get("token_info") or {}
        if tok.get("address") != TRON_USDT_CONTRACT:
            continue
        if str(tx.get("to") or "") != tron_addr:
            continue
        if str(tx.get("type") or "") not in ("Transfer", ""):
            continue
        try:
            decimals = int(tok.get("decimals", 6))
            raw_val = int(tx.get("value") or 0)
        except (TypeError, ValueError):
            continue
        usd = raw_val / (10**decimals)
        if usd >= 0.01:
            tx_id = str(tx.get("transaction_id") or "")
            if tx_id:
                inflows[f"tron_usdt:{tx_id}"] = usd

    for tx in trx_payload.get("data") or []:
        if not isinstance(tx, dict):
            continue
        ret = tx.get("ret") or []
        if not ret or ret[0].get("contractRet") != "SUCCESS":
            continue
        contracts = (tx.get("raw_data") or {}).get("contract") or []
        if not contracts or contracts[0].get("type") != "TransferContract":
            continue
        val = (contracts[0].get("parameter") or {}).get("value") or {}
        if str(val.get("to_address") or "").lower() != tron_hex:
            continue
        try:
            amount_sun = int(val.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        # Ignore < 0.1 TRX dust spam
        if amount_sun >= 100_000:
            tx_id = str(tx.get("txID") or "")
            if tx_id:
                inflows[f"tron_trx:{tx_id}"] = (amount_sun / 1_000_000.0) * trx_usd

    return inflows


def parse_eth_blockscout_inflows(
    evm_addr: str,
    tx_payload: dict,
    tok_payload: dict,
    eth_usd: float,
) -> dict[str, float]:
    inflows: dict[str, float] = {}
    addr_low = evm_addr.lower()

    for tx in tx_payload.get("items") or []:
        if not isinstance(tx, dict) or tx.get("status") != "ok":
            continue
        to_hash = str(((tx.get("to") or {}).get("hash")) or "").lower()
        if to_hash != addr_low:
            continue
        try:
            wei = int(tx.get("value") or 0)
        except (TypeError, ValueError):
            continue
        # Ignore < 0.00001 ETH dust
        if wei >= 10**13:
            tx_hash = str(tx.get("hash") or "").lower()
            if tx_hash:
                inflows[f"eth_native:{tx_hash}"] = (wei / 1e18) * eth_usd

    for tr in tok_payload.get("items") or []:
        if not isinstance(tr, dict):
            continue
        to_hash = str(((tr.get("to") or {}).get("hash")) or "").lower()
        if to_hash != addr_low:
            continue
        token = tr.get("token") or {}
        contract = str(token.get("address_hash") or "").lower()
        if contract not in ETH_STABLE_CONTRACTS:
            continue
        sym, default_dec = ETH_STABLE_CONTRACTS[contract]
        total = tr.get("total") or {}
        try:
            dec = int(total.get("decimals") or default_dec)
            raw_val = int(total.get("value") or 0)
        except (TypeError, ValueError):
            continue
        usd = raw_val / (10**dec)
        if usd >= 0.01:
            tx_hash = str(tr.get("transaction_hash") or "").lower()
            log_idx = str(tr.get("log_index") or "0")
            if tx_hash:
                inflows[f"eth_{sym.lower()}:{tx_hash}:{log_idx}"] = usd

    return inflows


def _rpc_call(rpc_url: str, method: str, params: list) -> object:
    res = _http_json(rpc_url, body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in res:
        raise RuntimeError(str(res["error"]))
    return res.get("result")


def poll_evm_l2_inflows(
    evm_addr: str,
    last_blocks: dict[str, int],
    eth_usd: float,
) -> tuple[dict[str, float], float]:
    inflows: dict[str, float] = {}
    live_balance_floor = 0.0
    addr_low = evm_addr.lower()
    padded_to = "0x" + ("0" * 24) + addr_low[2:]

    for chain, cfg in EVM_RPC_CONFIGS.items():
        rpc_url = str(cfg["rpc"])
        try:
            tip_hex = str(_rpc_call(rpc_url, "eth_blockNumber", []))
            tip = int(tip_hex, 16)
        except Exception:
            continue

        start_block = last_blocks.get(chain)
        if start_block is None:
            last_blocks[chain] = tip
            from_block = max(0, tip - 2000)
        else:
            from_block = start_block + 1
            last_blocks[chain] = tip

        # Query native ETH balance floor (in case direct L2 ETH arrived)
        try:
            bal_hex = str(_rpc_call(rpc_url, "eth_getBalance", [evm_addr, "latest"]))
            live_balance_floor += (int(bal_hex, 16) / 1e18) * eth_usd
        except Exception:
            pass

        if from_block <= tip:
            # Cap single scan window cleanly at 9000 blocks to stay within public RPC limits
            scan_start = max(from_block, tip - 9000)
            for token_addr, (sym, dec) in cfg["tokens"].items():
                try:
                    logs = _rpc_call(
                        rpc_url,
                        "eth_getLogs",
                        [
                            {
                                "fromBlock": hex(scan_start),
                                "toBlock": hex(tip),
                                "address": token_addr,
                                "topics": [ERC20_TRANSFER_TOPIC, None, padded_to],
                            }
                        ],
                    )
                except Exception:
                    continue
                if isinstance(logs, list):
                    for log in logs:
                        try:
                            val = int(str(log.get("data") or "0x0"), 16)
                        except ValueError:
                            continue
                        usd = val / (10**dec)
                        if usd >= 0.01:
                            txh = str(log.get("transactionHash") or "").lower()
                            idx = str(log.get("logIndex") or "0x0").lower()
                            if txh:
                                inflows[f"{chain}_{sym.lower()}:{txh}:{idx}"] = usd

    return inflows, live_balance_floor


def render_svg_badge(total_usd: float, tx_count: int) -> str:
    label = "Donations (50% -> Cancer Care)"
    value = f"${total_usd:,.2f} raised ({tx_count} tx)"
    l_w = len(label) * 6.8 + 20
    v_w = len(value) * 6.9 + 20
    total_w = int(round(l_w + v_w))
    lx = round(l_w / 2.0, 1)
    vx = round(l_w + v_w / 2.0, 1)
    l_esc = html.escape(label)
    v_esc = html.escape(value)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="24" role="img" '
        f'aria-label="{l_esc}: {v_esc}">\n'
        f'  <linearGradient id="g" x2="0" y2="100%">\n'
        f'    <stop offset="0" stop-color="#fff" stop-opacity=".08"/>\n'
        f'    <stop offset="1" stop-opacity=".12"/>\n'
        f'  </linearGradient>\n'
        f'  <clipPath id="r"><rect width="{total_w}" height="24" rx="5" fill="#fff"/></clipPath>\n'
        f'  <g clip-path="url(#r)">\n'
        f'    <rect width="{round(l_w, 1)}" height="24" fill="#24292f"/>\n'
        f'    <rect x="{round(l_w, 1)}" width="{round(v_w, 1)}" height="24" fill="#2ea043"/>\n'
        f'    <rect width="{total_w}" height="24" fill="url(#g)"/>\n'
        f'  </g>\n'
        f'  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="11" font-weight="600">\n'
        f'    <text x="{lx}" y="16">{l_esc}</text>\n'
        f'    <text x="{vx}" y="16">{v_esc}</text>\n'
        f'  </g>\n'
        f'</svg>\n'
    )


def render_svg_meter(
    total_usd: float,
    tx_count: int,
    tron_usd: float,
    evm_usd: float,
    updated_at_utc: str,
    lang: str = "en",
    mode: str = "dark",
) -> str:
    t = METER_THEMES[mode]
    s = METER_STRINGS[lang]
    is_rtl = s["dir"] == "rtl"
    goal, pct = compute_milestone_goal(total_usd)
    charity_usd = round(total_usd * 0.5, 2)
    maint_usd = round(max(0.0, total_usd - charity_usd), 2)
    ui_font = "system-ui, -apple-system, 'Segoe UI', Tahoma, Arial, sans-serif"
    mono_font = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

    if total_usd <= 0:
        pill_text = s["empty_pill"]
        pill_fill, pill_stroke, pill_fg = t["empty_badge_bg"], t["border"], t["empty_badge_fg"]
    elif pct >= 100.0:
        pill_text = s["full_pill"].format(total=total_usd)
        pill_fill, pill_stroke, pill_fg = t["panel"], t["amber"], t["amber"]
    else:
        pill_text = s["active_pill"].format(total=total_usd)
        pill_fill, pill_stroke, pill_fg = t["panel"], t["green"], t["green"]

    cup_fill_h = round(98.0 * pct / 100.0, 1)
    cup_fill_y = round(176.0 - cup_fill_h, 1)
    bar_w = round(608.0 * pct / 100.0, 1) if total_usd > 0 else 0.0
    if bar_w > 0:
        bar_w = max(8.0, bar_w)
    bar_rx = min(10.0, round(bar_w / 2.0, 1)) if bar_w > 0 else 0.0

    clip_id = f"cup-{lang}-{mode}"
    grad_id = f"bar-{lang}-{mode}"
    coffee_id = f"coffee-{lang}-{mode}"

    title_x, title_anchor = (816, "start") if is_rtl else (208, "start")
    pill_x = 208 if is_rtl else 636
    sub_x = 816 if is_rtl else 208
    bidi_attr = ' unicode-bidi="embed"' if is_rtl else ""
    dir_attr = s["dir"]
    utc_short = html.escape(updated_at_utc[:16].replace("T", " "))

    steam = ""
    if total_usd > 0:
        steam = (
            f'  <path d="M 86 68 Q 81 58 87 48 M 101 66 Q 96 55 102 45 M 116 68 Q 111 58 117 48" '
            f'fill="none" stroke="{t["amber"]}" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>\n'
        )
    else:
        steam = (
            f'  <line x1="74" y1="152" x2="128" y2="152" stroke="{t["border"]}" stroke-width="1.5" stroke-dasharray="4 3"/>\n'
        )

    cup_liquid = ""
    if cup_fill_h > 0:
        cup_liquid = (
            f'    <rect x="62" y="{cup_fill_y}" width="78" height="{cup_fill_h}" fill="url(#{coffee_id})"/>\n'
            f'    <rect x="62" y="{cup_fill_y}" width="78" height="4" fill="#d9a066" opacity="0.8"/>\n'
        )

    cup_badge_txt = f"{pct:.0f}%" if total_usd > 0 else s["empty_cup"]
    cup_badge_y = 154 if pct >= 28.0 else 128
    cup_badge_fg = "#ffffff" if pct >= 28.0 else t["muted"]
    split_pink = t["pink"] if total_usd > 0 else t["split_pink_dim"]
    split_blue = t["blue"] if total_usd > 0 else t["split_blue_dim"]
    filled_caption = html.escape(s["filled_cap"].format(pct=pct, goal=goal))
    milestone_txt = html.escape(s["milestone"].format(total=total_usd, goal=goal, pct=pct))
    split_txt = html.escape(s["split"].format(charity=charity_usd, maint=maint_usd))

    progress_fill = ""
    if bar_w > 0:
        progress_fill = (
            f'  <rect x="208" y="82" width="{bar_w}" height="20" rx="{bar_rx}" fill="url(#{grad_id})"/>\n'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="840" height="252" viewBox="0 0 840 252" '
        f'role="img" aria-label="{html.escape(s["aria"])}">\n'
        f'  <defs>\n'
        f'    <clipPath id="{clip_id}">\n'
        f'      <path d="M 64 78 L 138 78 L 132 162 Q 130 176 101 176 Q 72 176 70 162 Z"/>\n'
        f'    </clipPath>\n'
        f'    <linearGradient id="{grad_id}" x1="0" x2="1" y1="0" y2="0">\n'
        f'      <stop offset="0%" stop-color="{t["green"]}"/>\n'
        f'      <stop offset="100%" stop-color="{t["blue"]}"/>\n'
        f'    </linearGradient>\n'
        f'    <linearGradient id="{coffee_id}" x1="0" x2="0" y1="0" y2="1">\n'
        f'      <stop offset="0%" stop-color="#b07442"/>\n'
        f'      <stop offset="100%" stop-color="#6b3e1b"/>\n'
        f'    </linearGradient>\n'
        f'  </defs>\n'
        f'  <rect x="1" y="1" width="838" height="250" rx="12" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="1.5"/>\n'
        f'  <rect x="22" y="22" width="164" height="208" rx="10" fill="{t["panel"]}" stroke="{t["border"]}" stroke-width="1.2"/>\n'
        f'{steam}'
        f'  <g clip-path="url(#{clip_id})">\n'
        f'    <rect x="62" y="76" width="78" height="102" fill="{t["cup_empty"]}"/>\n'
        f'{cup_liquid}'
        f'  </g>\n'
        f'  <path d="M 64 78 L 138 78 L 132 162 Q 130 176 101 176 Q 72 176 70 162 Z" fill="none" stroke="{t["cup_outline"]}" stroke-width="2.6" stroke-linejoin="round"/>\n'
        f'  <path d="M 136 92 C 156 92 156 140 134 140" fill="none" stroke="{t["cup_outline"]}" stroke-width="4.2" stroke-linecap="round"/>\n'
        f'  <text x="101" y="{cup_badge_y}" fill="{cup_badge_fg}" font-family="{mono_font}" font-size="13" font-weight="700" text-anchor="middle">{html.escape(cup_badge_txt)}</text>\n'
        f'  <text x="104" y="209" fill="{t["text"]}" font-family="{ui_font}" font-size="11" font-weight="700" text-anchor="middle" direction="{dir_attr}"{bidi_attr}>{filled_caption}</text>\n'
        f'  <text x="{title_x}" y="44" fill="{t["text"]}" font-family="{ui_font}" font-size="15" font-weight="700" text-anchor="{title_anchor}" direction="{dir_attr}"{bidi_attr}>{html.escape(s["title"])}</text>\n'
        f'  <rect x="{pill_x}" y="25" width="180" height="26" rx="13" fill="{pill_fill}" stroke="{pill_stroke}" stroke-width="1.3"/>\n'
        f'  <text x="{pill_x + 90}" y="42" fill="{pill_fg}" font-family="{ui_font if is_rtl else mono_font}" font-size="11" font-weight="700" text-anchor="middle" direction="{dir_attr}"{bidi_attr}>{html.escape(pill_text)}</text>\n'
        f'  <text x="{sub_x}" y="72" fill="{t["muted"]}" font-family="{ui_font}" font-size="12" font-weight="600" text-anchor="start" direction="{dir_attr}"{bidi_attr}>{milestone_txt}</text>\n'
        f'  <rect x="208" y="82" width="608" height="20" rx="10" fill="{t["track"]}" stroke="{t["border"]}" stroke-width="1"/>\n'
        f'{progress_fill}'
        f'  <text x="208" y="116" fill="{t["muted"]}" font-family="{mono_font}" font-size="10" text-anchor="start">0%</text>\n'
        f'  <text x="360" y="116" fill="{t["muted"]}" font-family="{mono_font}" font-size="10" text-anchor="middle">25%</text>\n'
        f'  <text x="512" y="116" fill="{t["muted"]}" font-family="{mono_font}" font-size="10" text-anchor="middle">50%</text>\n'
        f'  <text x="664" y="116" fill="{t["muted"]}" font-family="{mono_font}" font-size="10" text-anchor="middle">75%</text>\n'
        f'  <text x="816" y="116" fill="{t["muted"]}" font-family="{mono_font}" font-size="10" text-anchor="end">100% (${goal:,})</text>\n'
        f'  <text x="{sub_x}" y="138" fill="{t["text"]}" font-family="{ui_font}" font-size="11" font-weight="600" text-anchor="start" direction="{dir_attr}"{bidi_attr}>{split_txt}</text>\n'
        f'  <rect x="208" y="147" width="303" height="12" rx="6" fill="{split_pink}"/>\n'
        f'  <rect x="513" y="147" width="303" height="12" rx="6" fill="{split_blue}"/>\n'
        f'  <rect x="208" y="176" width="192" height="46" rx="8" fill="{t["panel"]}" stroke="{t["border"]}" stroke-width="1"/>\n'
        f'  <text x="304" y="195" fill="{t["muted"]}" font-family="{ui_font}" font-size="10" font-weight="600" text-anchor="middle" direction="{dir_attr}"{bidi_attr}>{html.escape(s["tron_lbl"])}</text>\n'
        f'  <text x="304" y="213" fill="{t["text"]}" font-family="{mono_font}" font-size="13" font-weight="700" text-anchor="middle">${tron_usd:,.2f}</text>\n'
        f'  <rect x="416" y="176" width="192" height="46" rx="8" fill="{t["panel"]}" stroke="{t["border"]}" stroke-width="1"/>\n'
        f'  <text x="512" y="195" fill="{t["muted"]}" font-family="{ui_font}" font-size="10" font-weight="600" text-anchor="middle" direction="{dir_attr}"{bidi_attr}>{html.escape(s["evm_lbl"])}</text>\n'
        f'  <text x="512" y="213" fill="{t["text"]}" font-family="{mono_font}" font-size="13" font-weight="700" text-anchor="middle">${evm_usd:,.2f}</text>\n'
        f'  <rect x="624" y="176" width="192" height="46" rx="8" fill="{t["panel"]}" stroke="{t["border"]}" stroke-width="1"/>\n'
        f'  <text x="720" y="195" fill="{t["muted"]}" font-family="{ui_font}" font-size="10" font-weight="600" text-anchor="middle" direction="{dir_attr}"{bidi_attr}>{html.escape(s["tx_lbl"])}</text>\n'
        f'  <text x="720" y="213" fill="{t["text"]}" font-family="{mono_font}" font-size="11" font-weight="700" text-anchor="middle">{tx_count} tx · {utc_short}</text>\n'
        f'</svg>\n'
    )


def update_stats(
    tron_address: str,
    evm_address: str,
    state_path: Path,
    svg_path: Path,
    offline: bool = False,
) -> dict:
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    else:
        state = {}

    seen_txs: dict[str, float] = dict(state.get("seen_txs") or {})
    last_blocks: dict[str, int] = {k: int(v) for k, v in (state.get("last_blocks") or {}).items()}
    floor_usd = float(state.get("live_balance_floor_usd") or 0.0)

    if not offline:
        prices = fetch_usd_prices()
        try:
            trc20 = _http_json(
                f"https://api.trongrid.io/v1/accounts/{tron_address}/transactions/trc20?only_to=true&limit=200"
            )
            trx_txs = _http_json(
                f"https://api.trongrid.io/v1/accounts/{tron_address}/transactions?only_to=true&limit=200"
            )
            seen_txs.update(parse_tron_inflows(tron_address, trc20, trx_txs, prices["trx"]))
        except Exception:
            pass

        try:
            eth_txs = _http_json(
                f"https://eth.blockscout.com/api/v2/addresses/{evm_address}/transactions?filter=to"
            )
            eth_tok = _http_json(
                f"https://eth.blockscout.com/api/v2/addresses/{evm_address}/token-transfers?filter=to"
            )
            seen_txs.update(parse_eth_blockscout_inflows(evm_address, eth_txs, eth_tok, prices["eth"]))
        except Exception:
            pass

        l2_inflows, l2_floor = poll_evm_l2_inflows(evm_address, last_blocks, prices["eth"])
        seen_txs.update(l2_inflows)
        floor_usd = max(floor_usd, l2_floor)

    tron_usd, evm_usd, total_usd = compute_network_totals(seen_txs, floor_usd)
    tx_count = len(seen_txs)
    goal_usd, pct = compute_milestone_goal(total_usd)
    updated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out_state = {
        "updated_at_utc": updated_at_utc,
        "tron_address": tron_address,
        "evm_address": evm_address,
        "total_usd": total_usd,
        "tron_usd": tron_usd,
        "evm_usd": evm_usd,
        "charity_share_usd": round(total_usd * 0.5, 2),
        "milestone_goal_usd": goal_usd,
        "milestone_pct": pct,
        "tx_count": tx_count,
        "live_balance_floor_usd": round(floor_usd, 2),
        "last_blocks": last_blocks,
        "seen_txs": seen_txs,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(out_state, indent=2) + "\n", encoding="utf-8")
    svg_path.write_text(render_svg_badge(total_usd, tx_count), encoding="utf-8")

    meter_dir = svg_path.parent
    meter_variants = {
        "donation_meter_dark.svg": ("en", "dark"),
        "donation_meter_light.svg": ("en", "light"),
        "donation_meter_fa_dark.svg": ("fa", "dark"),
        "donation_meter_fa_light.svg": ("fa", "light"),
    }
    for fname, (mlang, mmode) in meter_variants.items():
        (meter_dir / fname).write_text(
            render_svg_meter(total_usd, tx_count, tron_usd, evm_usd, updated_at_utc, lang=mlang, mode=mmode),
            encoding="utf-8",
        )
    return out_state


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Watch-only on-chain donation stats & badge generator")
    parser.add_argument("--tron-address", default=DEFAULT_TRON_ADDRESS)
    parser.add_argument("--evm-address", default=DEFAULT_EVM_ADDRESS)
    parser.add_argument("--state-out", default="donation_stats.json")
    parser.add_argument("--svg-out", default="donation_badge.svg")
    parser.add_argument("--offline", action="store_true", help="Render badge from existing state file only")
    args = parser.parse_args()

    res = update_stats(
        tron_address=args.tron_address,
        evm_address=args.evm_address,
        state_path=Path(args.state_out),
        svg_path=Path(args.svg_out),
        offline=args.offline,
    )
    print(json.dumps({
        "total_usd": res["total_usd"],
        "charity_share_usd": res["charity_share_usd"],
        "tx_count": res["tx_count"],
        "updated_at_utc": res["updated_at_utc"],
    }))


if __name__ == "__main__":
    main()

