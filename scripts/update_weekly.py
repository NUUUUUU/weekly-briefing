#!/usr/bin/env python3
"""
Weekly Briefing Auto-Update Script - v4 (complete restore)
GitHub Actions가 매주 월요일 08:10 KST에 호출.
"""
import sys
print(">>> SCRIPT START <<<", flush=True)
print(f">>> Python: {sys.version}", flush=True)

import os
print(f">>> argv: {sys.argv}", flush=True)
print(f">>> cwd: {os.getcwd()}", flush=True)
print(f">>> env WEEK_OVERRIDE: {os.environ.get('WEEK_OVERRIDE', '(unset)')}", flush=True)
print(f">>> env TZ: {os.environ.get('TZ', '(unset)')}", flush=True)
print(">>> Importing stdlib modules...", flush=True)

import html as html_mod
import json
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

print(">>> Importing 3rd party modules (requests, bs4)...", flush=True)
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f">>> FATAL: Missing dependency: {e}", flush=True)
    sys.exit(1)
print(">>> All imports OK", flush=True)

# ---------- 설정 ----------
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_ROOT / "data" / "observations.json"
LAST_RUN_FILE = REPO_ROOT / "data" / "last_run.json"
TEMPLATE_FILE = REPO_ROOT / "templates" / "scorecard_template.html"
DOCS_DIR = REPO_ROOT / "docs"
INDEX_FILE = DOCS_DIR / "index.html"

print(f">>> REPO_ROOT: {REPO_ROOT}", flush=True)
print(f">>> DATA_FILE exists: {DATA_FILE.exists()}", flush=True)
print(f">>> TEMPLATE_FILE exists: {TEMPLATE_FILE.exists()}", flush=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

EXPECTED_RATE_RANGE = {
    "USD": (1000, 2500),
    "CNY": (150, 400),
    "JPY": (700, 1500),
    "EUR": (1300, 2500),
    "THB": (25, 80),
    "GBP": (1500, 3000),
}

EXPECTED_STOCK_RANGE = {
    "066570": (50000, 500000),
}

# ---------- 주차 계산 ----------
ANCHOR_DATE = datetime(2026, 5, 18).date()
ANCHOR_WEEK = 22


def monday_to_user_week(week_monday):
    delta_weeks = (week_monday - ANCHOR_DATE).days // 7
    return week_monday.year, ANCHOR_WEEK + delta_weeks


def user_week_to_monday(user_week, year):
    delta_weeks = user_week - ANCHOR_WEEK
    return ANCHOR_DATE + timedelta(weeks=delta_weeks)


def get_reporting_week():
    override = os.environ.get("WEEK_OVERRIDE", "").strip()
    today = NOW.date()
    if override.isdigit():
        user_week = int(override)
        week_monday = user_week_to_monday(user_week, today.year)
        week_sunday = week_monday + timedelta(days=6)
        range_str = f"{week_monday.strftime('%m/%d')}~{week_sunday.strftime('%m/%d')}"
        return today.year, user_week, week_monday, week_sunday, range_str
    days_since_monday = today.weekday()
    last_sunday = today - timedelta(days=days_since_monday + 1)
    last_monday = last_sunday - timedelta(days=6)
    year, user_week = monday_to_user_week(last_monday)
    range_str = f"{last_monday.strftime('%m/%d')}~{last_sunday.strftime('%m/%d')}"
    return year, user_week, last_monday, last_sunday, range_str


# ---------- 스크래핑 ----------
def parse_number(text):
    m = re.search(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?", text)
    if m:
        return float(m.group().replace(",", ""))
    return None


def fetch_naver_exchange(currency_code):
    url = f"https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_{currency_code}KRW"
    expected_min, expected_max = EXPECTED_RATE_RANGE.get(currency_code, (1, 100000))
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        candidates = []
        for label in soup.find_all(string=re.compile("매매기준율")):
            parent = label.find_parent(["tr", "div", "p", "li"])
            if not parent:
                continue
            for cell in parent.find_all(string=True):
                val = parse_number(str(cell))
                if val and expected_min <= val <= expected_max:
                    candidates.append(val)
        if not candidates:
            head = soup.select_one(".head_info")
            if head:
                for txt in head.find_all(string=True):
                    val = parse_number(str(txt))
                    if val and expected_min <= val <= expected_max:
                        candidates.append(val)
        if not candidates:
            for el in soup.find_all(["span", "em", "td", "strong", "div"]):
                txt = el.get_text(strip=True)
                val = parse_number(txt)
                if val and expected_min <= val <= expected_max:
                    candidates.append(val)
        if candidates:
            most_common = Counter(candidates).most_common(1)[0][0]
            print(f"  [DEBUG] {currency_code}/KRW candidates={len(candidates)}, picked={most_common}", flush=True)
            return most_common
        print(f"  [WARN] {currency_code}/KRW: no value in range [{expected_min}, {expected_max}]", flush=True)
    except Exception as e:
        print(f"  [WARN] {currency_code}/KRW fetch failed: {e}", flush=True)
    return None


def fetch_naver_stock(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    expected_min, expected_max = EXPECTED_STOCK_RANGE.get(code, (100, 10000000))
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        candidates = []
        node = soup.select_one(".no_today")
        if node:
            val = parse_number(node.get_text(" ", strip=True))
            if val and expected_min <= val <= expected_max:
                return int(val)
        for el in soup.find_all(["span", "em", "td", "strong"]):
            txt = el.get_text(strip=True)
            val = parse_number(txt)
            if val and expected_min <= val <= expected_max:
                candidates.append(val)
        if candidates:
            return int(Counter(candidates).most_common(1)[0][0])
        print(f"  [WARN] stock {code}: no value in range", flush=True)
    except Exception as e:
        print(f"  [WARN] stock {code} fetch failed: {e}", flush=True)
    return None


# ---------- 데이터 적재 ----------
def load_observations():
    if not DATA_FILE.exists():
        print(f">>> FATAL: observations.json 없음: {DATA_FILE}", flush=True)
        sys.exit(2)
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_observations(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_observation(obs, key, date_str, value, observed=True):
    if value is None:
        return False
    ind = obs.get("indicators", {}).get(key)
    if not ind:
        print(f"  [WARN] unknown indicator key: {key}", flush=True)
        return False
    for p in ind.get("data", []):
        if p["date"] == date_str:
            return False
    ind.setdefault("data", []).append({"date": date_str, "value": value, "observed": observed})
    ind["data"].sort(key=lambda p: p["date"])
    return True


def auto_update_meta(ind):
    data = ind.get("data", [])
    if len(data) < 1:
        return
    latest = data[-1]
    prev = data[-2] if len(data) > 1 else None
    val_str = f"{latest['value']:,}" if isinstance(latest["value"], (int, float)) else str(latest["value"])
    parts = [f"최신 {val_str} ({latest['date']})"]
    if prev:
        delta = latest["value"] - prev["value"]
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "→"
        parts.append(f"전 {prev['value']:,} ({arrow}{delta:+.2f})")
    ind["meta"] = " · ".join(parts) + " · (자동)"


# ---------- HTML 렌더링 ----------
def render_card(key, ind):
    badge = ind.get("badge", "stale")
    badge_text = html_mod.escape(ind.get("badge_text", "—"))
    monthly_badge = '<span class="badge monthly-only">월간 전용</span>' if ind.get("monthly_only") else ""
    label = html_mod.escape(ind.get("label", key))
    unit_label = ind.get("unit_label", "")
    if unit_label:
        label_full = f'{label} <span style="font-size:10px;color:#9ca3af;font-weight:normal;">({html_mod.escape(unit_label)})</span>'
    else:
        label_full = label
    meta = html_mod.escape(ind.get("meta", ""))
    links_html = " ".join(
        f'<a href="{html_mod.escape(l["url"])}" target="_blank">{html_mod.escape(l["text"])}</a>'
        for l in ind.get("links", [])
    )
    note = ind.get("note", "")
    note_class = "note warn" if ind.get("note_warn") else "note"
    note_html = f'<div class="{note_class}">{html_mod.escape(note)}</div>' if note else ""
    return (
        f'  <div class="card">\n'
        f'    <h3>{label_full} <span class="badge {badge}">{badge_text}</span>{monthly_badge}</h3>\n'
        f'    <div class="meta">{meta}</div>\n'
        f'    <div class="canvas-wrap"><canvas id="ch_{key}"></canvas></div>\n'
        f'    <div class="point-count" id="pc_{key}"></div>\n'
        f'    <div class="links">{links_html}</div>\n'
        f'    {note_html}\n'
        f'  </div>'
    )


def render_html(obs, year, week, range_str):
    if not TEMPLATE_FILE.exists():
        print(f">>> FATAL: template 없음: {TEMPLATE_FILE}", flush=True)
        sys.exit(3)
    tpl = TEMPLATE_FILE.read_text(encoding="utf-8")
    indicators = obs.get("indicators", {})
    raw_data = {}
    for key, ind in indicators.items():
        bucket = "monthly" if ind.get("monthly_only") else "daily"
        raw_data[key] = {bucket: [[p["date"], p["value"], p["observed"]] for p in ind.get("data", [])]}
    cards_config = {}
    for key, ind in indicators.items():
        cards_config[f"ch_{key}"] = {
            "key": key,
            "label": ind.get("label", key),
            "color": ind.get("color", "#6b7280"),
            "monthlyOnly": bool(ind.get("monthly_only")),
        }
    cards_html = "\n".join(render_card(k, v) for k, v in indicators.items())
    today_str = NOW.date().isoformat()
    html = tpl
    html = html.replace("__RAW_DATA__", json.dumps(raw_data, ensure_ascii=False))
    html = html.replace("__CARDS_CONFIG__", json.dumps(cards_config, ensure_ascii=False))
    html = html.replace("__CARDS__", cards_html)
    html = html.replace("__WEEK__", str(week))
    html = html.replace("__YEAR__", str(year))
    html = html.replace("__RANGE__", range_str)
    html = html.replace("__UPDATED_AT__", NOW.strftime("%Y-%m-%d %H:%M KST"))
    html = html.replace("__TODAY__", today_str)
    return html


def update_index(year, week, range_str):
    if not INDEX_FILE.exists():
        print(f"  [WARN] index.html 없음, skip", flush=True)
        return
    html = INDEX_FILE.read_text(encoding="utf-8")
    html = re.sub(r'(<a href="\./\d+w\.html">[^<]*?) — 최신', r'\1', html, count=1)
    if f'href="./{week}w.html"' in html:
        return
    new_entry = (
        f'\n  <li>\n'
        f'    <a href="./{week}w.html">{week}주차 ({range_str}) — 최신</a>\n'
        f'    <div class="desc">자동 갱신 {NOW.strftime("%Y-%m-%d %H:%M KST")}</div>\n'
        f'  </li>'
    )
    html = re.sub(r'(<ul class="list">)', r'\1' + new_entry, html, count=1)
    INDEX_FILE.write_text(html, encoding="utf-8")



def save_last_run(year, week, range_str, fetched_keys):
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(
        json.dumps({
            "year": year,
            "week": week,
            "range": range_str,
            "timestamp": NOW.isoformat(),
            "fetched_keys": fetched_keys,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    print(f"=== Weekly Briefing Update - {NOW.isoformat()} ===", flush=True)
    year, week, week_monday, week_sunday, range_str = get_reporting_week()
    print(f"Reporting week: {year} W{week} ({range_str})", flush=True)
    obs = load_observations()
    target_date = week_sunday.isoformat()

    print("\n--- Data fetch attempts ---", flush=True)
    fetched_keys = []

    val = fetch_naver_exchange("USD")
    if val:
        print(f"  USD/KRW: {val}", flush=True)
        if append_observation(obs, "usdkrw", target_date, val):
            fetched_keys.append("usdkrw")
    time.sleep(1)

    val = fetch_naver_exchange("CNY")
    if val:
        print(f"  CNY/KRW: {val}", flush=True)
        if append_observation(obs, "cnykrw", target_date, val):
            fetched_keys.append("cnykrw")
    time.sleep(1)

    val = fetch_naver_stock("066570")
    if val:
        print(f"  LG: {val}", flush=True)
        if append_observation(obs, "lge", target_date, val):
            fetched_keys.append("lge")

    print(f"\nTotal {len(fetched_keys)} new points: {fetched_keys}", flush=True)

    for key in fetched_keys:
        ind = obs["indicators"].get(key)
        if ind:
            auto_update_meta(ind)
            ind["badge_text"] = f"{week_sunday.strftime('%m/%d')} D"
            ind["badge"] = "fresh"

    obs["metadata"] = {
        **obs.get("metadata", {}),
        "updated_at": NOW.isoformat(),
        "reporting_week": week,
        "year": year,
        "auto_run": True,
        "last_fetched": fetched_keys,
    }
    save_observations(obs)
    print(f"saved {DATA_FILE.relative_to(REPO_ROOT)}", flush=True)

    html = render_html(obs, year, week, range_str)
    output_path = DOCS_DIR / f"{week}w.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"generated {output_path.relative_to(REPO_ROOT)}", flush=True)

    update_index(year, week, range_str)
    print(f"updated {INDEX_FILE.relative_to(REPO_ROOT)}", flush=True)

    save_last_run(year, week, range_str, fetched_keys)
    print(f"saved {LAST_RUN_FILE.relative_to(REPO_ROOT)}", flush=True)

    print("\n=== Done ===", flush=True)


print(">>> Module loaded. __name__ =", __name__, flush=True)

if __name__ == "__main__":
    print(">>> Calling main()...", flush=True)
    try:
        main()
        print(">>> main() completed successfully", flush=True)
    except Exception as e:
        import traceback
        print(f">>> EXCEPTION in main(): {e}", flush=True)
        traceback.print_exc()
        raise
    print(">>> SCRIPT END <<<", flush=True)
