# OPENCLAW AI Unit
WK마케팅그룹 삼국지 + 그리스 신화 AI 부대

## 부대 현황
| 봇 | PC | 상태 |
|---|---|---|
| WK유비 | 회사PC | 점검 필요 |
| WK관우 | 4호기 | ✅ v2 |
| WK공명 | 회사 노트북 | ✅ |
| WK장비 | 개인 노트북 | ✅ v2 |
| WK자룡 | 10호기 | ✅ |
| WK중달 | 9호기 | ✅ |
| WK방통 | 집PC (LEADER) | ✅ v2 |
| WK에이트 | 8호기 | ✅ |
| WK비너스 | 5호기 | 미배포 |
| WK헬레나 | 2호기 | 미배포 |
| WK제이슨 | 7호기 | 미배포 |

## 구조
```
openclaw/
├── bot/           ← 봇 코드 (PC별로 다름)
│   ├── wk_bot.py        ← 표준 봇 / 리더봇
│   ├── WATCHDOG.bat     ← 자동 복구
│   └── AUTOSTART.bat    ← 부팅 자동실행
├── scripts/       ← 공용 스크립트
│   ├── wk_bot_template_v2.py  ← 부대원 표준 템플릿
│   ├── auto_patch_v2.py       ← 자동 패치 스크립트
│   └── diagnose.ps1           ← PC 진단
├── workspace/     ← AI 작업 파일
├── backup/        ← 코드 백업
└── logs/          ← 로그
```

## 표준 세팅 (모든 PC)
1. 덮개 닫아도 작동 (LIDACTION=0)
2. Watchdog 자동 복구 (10초)
3. 부팅 시 자동실행
4. 절전 모드 해제
5. 고성능 전원

## 봇 버전
- v1: DM 전용
- v2: 그룹 반응 + 리더봇 관리 시스템
