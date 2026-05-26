# Weekly Briefing — Macro Scorecard

주간 매크로·원가 지표 추세를 자동 수집하여 GitHub Pages에 호스팅.
Notion 경영 브리핑에 임베드되어 매주 자동 갱신.

## 🌐 Live URLs

- 인덱스: https://nuuuuuu.github.io/weekly-briefing/
- 최신 주차 (자동 생성): https://nuuuuuu.github.io/weekly-briefing/{주차번호}w.html

## ⚙️ 자동화 (GitHub Actions)

| 항목 | 값 |
|---|---|
| 실행 주기 | **매주 월요일 08:10 KST** (cron `10 23 * * 0` UTC) |
| 트리거 | 스케줄 자동 + 수동(`Actions` 탭 → `Run workflow`) |
| 권한 | `GITHUB_TOKEN` (자동 발급, PAT 불요) |
| Python | 3.11 |
| 의존성 | `requests`, `beautifulsoup4`, `lxml` |

### 동작 단계

1. **보고 주차 계산** — `today.weekday()` 기반으로 직전 ISO 주차 산출 (예: 월요일 08:10 실행 시 직전 일요일~월요일 주차)
2. **데이터 수집** — Naver Finance에서 다음 종가 스크래핑 시도:
   - USD/KRW 매매기준율
   - CNY/KRW 매매기준율
   - LG전자(066570) 종가
3. **observations.json 갱신** — 동일 날짜 데이터 중복 시 skip
4. **HTML 생성** — `templates/scorecard_template.html` + JSON → `docs/{week}w.html`
5. **index.html 업데이트** — 최신 주차 링크 자동 추가
6. **자동 커밋·푸시** — `github-actions[bot]` 명의

### 수동 실행

```
Actions 탭 → "Weekly Briefing Auto-Update" → "Run workflow" 클릭
→ (선택) week_override 입력 후 실행
```

## 📁 폴더 구조

```
weekly-briefing/
├── .github/workflows/
│   └── weekly.yml              # GitHub Actions 워크플로우
├── scripts/
│   └── update_weekly.py        # 데이터 수집 + HTML 생성
├── templates/
│   └── scorecard_template.html # HTML 템플릿 (placeholders 포함)
├── data/
│   └── observations.json       # 누적 관측 데이터 (필수, 절대 수동 삭제 금지)
├── docs/                       # GitHub Pages 소스
│   ├── index.html              # 주차 목록 (자동 갱신)
│   ├── 22w.html                # 주차별 HTML (자동 생성)
│   └── ...
└── README.md
```

## 📊 데이터 소스

| 지표 | 자동 수집 | 출처 |
|---|---|---|
| USD/KRW | ✅ | Naver Finance (매매기준율) |
| CNY/KRW | ✅ | Naver Finance |
| THB/KRW | ❌ | ECOS API 키 필요 (TODO) |
| USD/EGP | ❌ | Trading Economics (TODO: Selenium or API) |
| HRC 열연 | ❌ | 하나증권 Weekly (수동 입력) |
| CRC 냉연 | ❌ | 포스코 IR (수동, 분기 단위) |
| LME 알루미늄 | ❌ | LME (유료) 또는 Investing.com (TODO) |
| LG전자 주가 | ✅ | Naver Finance (066570) |
| 한국 PMI | ❌ | S&P Global (월간, 수동) |
| 중국 PMI | ❌ | NBS (월간, 수동) |

자동 수집되지 않는 지표는 `data/observations.json`을 직접 편집하여 갱신.

## 🔧 수동 데이터 입력 방법

1. `data/observations.json` 열기
2. 해당 지표의 `data` 배열에 새 항목 추가:
   ```json
   {"date": "2026-06-01", "value": 95.5, "observed": true}
   ```
3. Commit & Push → 다음 자동 빌드 시 반영, 또는 즉시 `Run workflow`로 강제 빌드

## 🔒 보안 원칙

- 본 레포는 **공개 매크로 지표만** 호스팅
- 회사·고객사 단가·발주 정보 등 기밀 데이터는 **절대 포함하지 않음**
- 모든 해석·영향 코멘트는 내부 Notion에만 보관
- API 키 등 시크릿은 GitHub Secrets에만 저장 (코드에 평문 금지)

## 📈 신선도 배지 의미

- 🟢 `fresh` — 당주 직접 관측
- 🟡 `stale` — 직전 월 또는 직전 관측
- 🔴 `lag` — 미수집(추정 또는 직전 일 데이터)
- 🟦 `monthly-only` — 월간 지표 (PMI 등)

## 🛠 로컬 테스트

```bash
# 의존성 설치
pip install requests beautifulsoup4 lxml

# 수동 실행 (현재 주차)
python scripts/update_weekly.py

# 특정 주차 강제 생성
WEEK_OVERRIDE=23 python scripts/update_weekly.py
```

## 라이선스

내부 사용 (사내 경영 브리핑 보조).
