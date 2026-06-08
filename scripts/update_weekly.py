#!/usr/bin/env python3
"""Weekly Briefing Auto-Update v6 — country 필드 + 12개 지표"""
import sys
print(">>> SCRIPT START <<<", flush=True)
import os
import html as html_mod
import json
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f">>> FATAL: {e}", flush=True)
    sys.exit(1)

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_ROOT / "data" / "observations.json"
LAST_RUN_FILE = REPO_ROOT / "data" / "last_run.json"
TEMPLATE_FILE = REPO_ROOT / "templates" / "scorecard_template.html"
DOCS_DIR = REPO_ROOT / "docs"
INDEX_FILE = DOCS_DIR / "index.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

EXPECTED_RATE_RANGE = {
    "USD": (1000, 2500), "CNY": (150, 400), "JPY": (700, 1500),
    "EUR": (1300, 2500), "THB": (25, 80), "GBP": (1500, 3000),
}
EXPECTED_STOCK_RANGE = {"066570": (50000, 500000)}

# 주차 컨벤션 앵커
ANCHOR_DATE = datetime(2026, 5, 18).date()
ANCHOR_WEEK = 22

COUNTRY_LABEL = {"ALL": "전체", "KR": "🇰🇷", "CN": "🇨🇳", "TH": "🇹🇭", "EG": "🇪🇬"}


def monday_to_user_week(week_monday):
    delta_weeks = (week_monday - ANCHOR_DATE).days // 7
    return week_monday.year, ANCHOR_WEEK + delta_weeks


def user_week_to_monday(user_week, year):
    return ANCHOR_DATE + timedelta(weeks=user_week - ANCHOR_WEEK)


def get_reporting_week():
    override = os.environ.get("WEEK_OVERRIDE", "").strip()
    today = NOW.date()
    if override.isdigit():
        uw = int(override)
        wm = user_week_to_monday(uw, today.year)
        ws = wm + timedelta(days=6)
        return today.year, uw, wm, ws, f"{wm.strftime('%m/%d')}~{ws.strftime('%m/%d')}"
    dsm = today.weekday()
    ls = today - timedelta(days=dsm + 1)
    lm = ls - timedelta(days=6)
    y, uw = monday_to_user_week(lm)
    return y, uw, lm, ls, f"{lm.strftime('%m/%d')}~{ls.strftime('%m/%d')}"


def parse_number(text):
    m = re.search(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?", text)
    return float(m.group().replace(",", "")) if m else None


def fetch_naver_exchange(currency_code):
    url = f"https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_{currency_code}KRW"
    lo, hi = EXPECTED_RATE_RANGE.get(currency_code, (1, 100000))
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        cand = []
        for lbl in soup.find_all(string=re.compile("매매기준율")):
            p = lbl.find_parent(["tr", "div", "p", "li"])
            if p:
                for c in p.find_all(string=True):
                    v = parse_number(str(c))
                    if v and lo <= v <= hi:
                        cand.append(v)
        if not cand:
            head = soup.select_one(".head_info")
            if head:
                for t in head.find_all(string=True):
                    v = parse_number(str(t))
                    if v and lo <= v <= hi:
                        cand.append(v)
        if not cand:
            for el in soup.find_all(["span", "em", "td", "strong", "div"]):
                v = parse_number(el.get_text(strip=True))
                if v and lo <= v <= hi:
                    cand.append(v)
        if cand:
            return Counter(cand).most_common(1)[0][0]
    except Exception as e:
        print(f"  [WARN] {currency_code}/KRW fetch failed: {e}", flush=True)
    return None


def fetch_naver_stock(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    lo, hi = EXPECTED_STOCK_RANGE.get(code, (100, 10000000))
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        node = soup.select_one(".no_today")
        if node:
            v = parse_number(node.get_text(" ", strip=True))
            if v and lo <= v <= hi:
                return int(v)
        cand = []
        for el in soup.find_all(["span", "em", "td", "strong"]):
            v = parse_number(el.get_text(strip=True))
            if v and lo <= v <= hi:
                cand.append(v)
        if cand:
            return int(Counter(cand).most_common(1)[0][0])
    except Exception as e:
        print(f"  [WARN] stock {code} fetch failed: {e}", flush=True)
    return None


def load_observations():
    if not DATA_FILE.exists():
        print(f">>> FATAL: observations.json 없음", flush=True)
        sys.exit(2)
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_observations(d):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def append_observation(obs, key, date_str, value, observed=True):
    if value is None:
        return False
    ind = obs.get("indicators", {}).get(key)
    if not ind:
        return False
    for p in ind.get("data", []):
        if p["date"] == date_str:
            return False
    ind.setdefault("data", []).append({"date": date_str, "value": value, "observed": observed})
    ind["data"].sort(key=lambda p: p["date"])
    return True


def auto_update_meta(ind):
    data = ind.get("data", [])
    if not data:
        return
    latest = data[-1]
    prev = data[-2] if len(data) > 1 else None
    vs = f"{latest['value']:,}" if isinstance(latest["value"], (int, float)) else str(latest["value"])
    parts = [f"최신 {vs} ({latest['date']})"]
    if prev:
        d = latest["value"] - prev["value"]
        a = "▲" if d > 0 else "▼" if d < 0 else "→"
        parts.append(f"전 {prev['value']:,} ({a}{d:+.2f})")
    ind["meta"] = " · ".join(parts) + " · (자동)"


def render_card(key, ind):
    badge = ind.get("badge", "stale")
    bt = html_mod.escape(ind.get("badge_text", "—"))
    mo_badge = '<span class="badge monthly-only">월간</span>' if ind.get("monthly_only") else ""
    country = ind.get("country", "ALL")
    country_label = COUNTRY_LABEL.get(country, country)
    c_badge = f'<span class="badge country">{country_label}</span>'
    label = html_mod.escape(ind.get("label", key))
    meta = html_mod.escape(ind.get("meta", ""))
    links = " ".join(
        f'<a href="{html_mod.escape(l["url"])}" target="_blank">{html_mod.escape(l["text"])}</a>'
        for l in ind.get("links", [])
    )
    note = ind.get("note", "")
    nc = "note warn" if ind.get("note_warn") else "note"
    nh = f'<div class="{nc}">{html_mod.escape(note)}</div>' if note else ""
    return (
        f'  <div class="card" id="card_{key}" data-country="{country}">\n'
        f'    <h3>{label} {c_badge}<span class="badge {badge}">{bt}</span>{mo_badge}</h3>\n'
        f'    <div class="meta">{meta}</div>\n'
        f'    <div class="canvas-wrap"><canvas id="ch_{key}"></canvas></div>\n'
        f'    <div class="point-count" id="pc_{key}"></div>\n'
        f'    <div class="links">{links}</div>\n'
        f'    {nh}\n'
        f'  </div>'
    )


def render_html(obs, year, week, range_str):
    if not TEMPLATE_FILE.exists():
        print(f">>> FATAL: template 없음", flush=True)
        sys.exit(3)
    tpl = TEMPLATE_FILE.read_text(encoding="utf-8")
    inds = obs.get("indicators", {})
    raw = {}
    cfg = {}
    for k, ind in inds.items():
        bucket = "monthly" if ind.get("monthly_only") else "daily"
        raw[k] = {bucket: [[p["date"], p["value"], p["observed"]] for p in ind.get("data", [])]}
        cfg[f"ch_{k}"] = {
            "key": k,
            "label": ind.get("label", k),
            "color": ind.get("color", "#6b7280"),
            "monthlyOnly": bool(ind.get("monthly_only")),
            "country": ind.get("country", "ALL"),
        }
    cards_html = "\n".join(render_card(k, v) for k, v in inds.items())
    html = tpl
    html = html.replace("__RAW_DATA__", json.dumps(raw, ensure_ascii=False))
    html = html.replace("__CARDS_CONFIG__", json.dumps(cfg, ensure_ascii=False))
    html = html.replace("__CARDS__", cards_html)
    html = html.replace("__WEEK__", str(week))
    html = html.replace("__YEAR__", str(year))
    html = html.replace("__RANGE__", range_str)
    html = html.replace("__UPDATED_AT__", NOW.strftime("%Y-%m-%d %H:%M KST"))
    html = html.replace("__TODAY__", NOW.date().isoformat())
    return html


def update_index(year, week, range_str):
    if not INDEX_FILE.exists():
        return
    html = INDEX_FILE.read_text(encoding="utf-8")
    html = re.sub(r'(<a href="\./\d+w\.html">[^<]*?) — 최신', r'\1', html, count=1)
    if f'href="./{week}w.html"' in html:
        return
    entry = f'\n  <li>\n    <a href="./{week}w.html">{week}주차 ({range_str}) — 최신</a>\n    <div class="desc">자동 갱신 {NOW.strftime("%Y-%m-%d %H:%M KST")}</div>\n  </li>'
    html = re.sub(r'(<ul class="list">)', r'\1' + entry, html, count=1)
    INDEX_FILE.write_text(html, encoding="utf-8")


def save_last_run(year, week, range_str, fetched):
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(
        json.dumps({"year": year, "week": week, "range": range_str,
                    "timestamp": NOW.isoformat(), "fetched_keys": fetched},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main():
    print(f"=== Weekly Briefing v6 — {NOW.isoformat()} ===", flush=True)
    y, w, wm, ws, rs = get_reporting_week()
    print(f"Reporting week: {y} W{w} ({rs})", flush=True)
    obs = load_observations()
    tgt = ws.isoformat()
    fetched = []

    print("\n--- Naver 스크래핑 ---", flush=True)
    v = fetch_naver_exchange("USD")
    if v and append_observation(obs, "usdkrw", tgt, v):
        fetched.append("usdkrw")
        print(f"  USD/KRW: {v}", flush=True)
    time.sleep(1)
    v = fetch_naver_exchange("CNY")
    if v and append_observation(obs, "cnykrw", tgt, v):
        fetched.append("cnykrw")
        print(f"  CNY/KRW: {v}", flush=True)
    time.sleep(1)
    v = fetch_naver_stock("066570")
    if v and append_observation(obs, "lge", tgt, v):
        fetched.append("lge")
        print(f"  LG: {v}", flush=True)

    print(f"\nTotal {len(fetched)} new: {fetched}", flush=True)
    for k in fetched:
        ind = obs["indicators"].get(k)
        if ind:
            auto_update_meta(ind)
            ind["badge_text"] = f"{ws.strftime('%m/%d')} D"
            ind["badge"] = "fresh"

    obs["metadata"] = {**obs.get("metadata", {}), "updated_at": NOW.isoformat(),
                       "reporting_week": w, "year": y, "auto_run": True,
                       "last_fetched": fetched}
    save_observations(obs)
    print(f"saved data/observations.json", flush=True)

    html = render_html(obs, y, w, rs)
    out = DOCS_DIR / f"{w}w.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"generated docs/{w}w.html", flush=True)

    update_index(y, w, rs)
    save_last_run(y, w, rs, fetched)
    print("=== Done ===", flush=True)


print(">>> __name__ =", __name__, flush=True)
if __name__ == "__main__":
    print(">>> Calling main()...", flush=True)
    try:
        main()
        print(">>> SUCCESS", flush=True)
    except Exception as e:
        import traceback
        print(f">>> EXCEPTION: {e}", flush=True)
        traceback.print_exc()
        raise
