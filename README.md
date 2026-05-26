# Weekly Briefing — Macro Scorecard

주간 매크로·원가 지표 추세를 GitHub Pages에서 호스팅하는 정적 대시보드.
경영 브리핑(Notion)에 embed되어 갱신됨.

## Live URL

https://nuuuuuu.github.io/weekly-briefing/

- 최신: [Week 22](https://nuuuuuu.github.io/weekly-briefing/22w.html)

## 데이터 출처

| 지표 | 출처 | 갱신 주기 |
|---|---|---|
| USD/KRW · CNY/KRW · THB/KRW | BOK ECOS / Naver Finance | Daily |
| USD/EGP | Trading Economics / CBE | Daily |
| HRC 열연 (Korea) | Hana Securities Weekly | Weekly |
| CRC 냉연 (POSCO) | 언론·IR | Quarterly |
| LME Aluminium 3M | LME / Investing.com | Daily |
| LG Electronics 주가 | KRX | Daily |
| Korea / China PMI | S&P Global / NBS | Monthly |

## 폴더 구조

```
weekly-briefing/
├── docs/                  # GitHub Pages source (publish here)
│   ├── index.html         # Landing page
│   └── 22w.html           # Week 22 scorecard
├── data/                  # (TBD) Raw CSVs
├── scripts/               # (TBD) Data collection scripts
└── .github/workflows/     # (TBD) Auto-update workflow
```

## 보안 원칙

- 본 레포는 **공개 매크로 지표만** 호스팅.
- 회사·고객사 단가·발주 정보 등 기밀 데이터는 **절대 포함하지 않음**.
- 모든 해석·영향 코멘트는 내부 Notion에만 보관.

## 라이선스

내부 사용 (사내 경영 브리핑 보조).
