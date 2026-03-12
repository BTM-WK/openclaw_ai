# OPENCLAW AI v6 - Autonomous Agent System
WK마케팅그룹 삼국지 + 그리스 신화 AI 부대

## 부대 현황
| 봇 | PC | 버전 | 상태 |
|---|---|---|---|
| WK유비 | 회사PC (D:\openclaw) | v5 | 배치완료 |
| WK관우 | 4호기 노트북 (C:\openclaw) | v5 | 배치완료 |
| WK공명 | 회사 노트북 (1호기) | v5 | 배치완료 |
| WK장비 | 개인 노트북 (D:\openclaw) | **v6** | ✅ Multi-AI |
| WK자룡 | 10호기 (oc10) | v5 | 배치완료 |
| WK중달 | 9호기 (oc9) | v5 | 배치완료 |
| WK방통 | 집PC (C:\openclaw) LEADER | **v6** | ✅ Multi-AI |
| WK에이트 | 8호기 | v5 | 배치완료 |
| WK비너스 | 5호기 | - | 미배치 |
| WK헬레나 | 2호기 | - | 미배치 |
| WK제이슨 | 7호기 | - | 미배치 |

## v6 아키텍처 (3-Thread)
```
Thread 1: Telegram Polling    — 메시지 수신/응답 (기존)
Thread 2: Autonomous Worker   — task_queue 기반 자율 작업 (신규)
Thread 3: Scheduler           — 주기 보고 + stall 감지 (신규)
```

## v6 핵심 기능
- **AI Router**: 작업 유형별 최적 AI 자동 선택 (Claude/Gemini/GPT)
- **Open WebUI 자동 설치/시작**: 없으면 pip install → 서버 시작
- **자율 작업 루프**: /mission 명령으로 목표 주면 AI가 task 분해 → 자동 실행
- **주기 보고**: Telegram + Gmail로 진행 상황 자동 보고
- **Stall 감지**: 30분 이상 산출물 없으면 경고

## 파일 구조
```
openclaw/
├── bot/
│   ├── wk_bot_v6.py         ← 메인 봇 (v6)
│   ├── ai_router.py          ← 멀티 AI 라우터
│   ├── autonomous_worker.py   ← 자율 작업 루프
│   ├── task_manager.py        ← task queue 관리
│   ├── reporter.py            ← 주기 보고 + Gmail
│   ├── setup_openwebui.py     ← Open WebUI 자동 설치/시작
│   ├── config.json            ← 봇별 설정 (git 제외)
│   ├── WATCHDOG.bat           ← 자동 복구
│   └── AUTOSTART.bat          ← 부팅 자동실행
├── workspace/                 ← AI 작업 파일
├── backup/                    ← 코드 백업
├── logs/                      ← 로그
└── usb_deploy/                ← USB 배포 키트 (git 제외)
    ├── install_v6.py          ← 올인원 설치 스크립트
    └── python-3.11.9-amd64.exe
```

## Telegram 명령어 (v6)
| 명령 | 기능 |
|---|---|
| /start | 봇 초기화 + 명령어 목록 |
| /mission <목표> | 자율 작업 시작 (AI가 task 자동 분해) |
| /addtask <설명> | task 수동 추가 |
| /status | 진행 현황 보고 |
| /tasks | task queue 전체 |
| /models | 사용 가능 AI 모델 + 라우팅 현황 |
| /route <메시지> | AI 라우팅 미리보기 |
| /pause /resume | 자율 작업 제어 |
| /report | 즉시 보고 |
| /openwebui | Open WebUI 상태/제어 |

## AI 라우팅 규칙
| 카테고리 | Open WebUI 있을 때 | 없을 때 |
|---|---|---|
| strategy | Claude (Anthropic) | Claude |
| research | Gemini 2.5 Pro (OpenWebUI) | Claude fallback |
| coding | Claude | Claude |
| writing | Claude | Claude |
| creative | Gemini 2.5 Pro (OpenWebUI) | Claude fallback |
| translation | Gemini 2.5 Pro (OpenWebUI) | Claude fallback |
| data_analysis | Claude | Claude |
| general | Claude | Claude |

## USB 설치 (다른 PC)
1. usb_deploy 폴더를 USB에 복사
2. 대상 PC에서 `python install_v6.py` 실행
3. Python 3.11 자동 설치 → 패키지 → v6 코드 → config 설정
4. 첫 실행 시 Open WebUI 자동 설치
5. 끝

## 표준 세팅 (모든 PC)
1. 덮개 닫아도 작동 (LIDACTION=0)
2. Watchdog 자동 복구 (10초)
3. 부팅 시 자동실행 (Startup 폴더)
4. 절전 모드 해제
5. 고성능 전원
6. Python 3.11.9 (C:\Python311)

## 봇 버전 이력
- v1: DM 전용
- v2: 그룹 반응 + 리더봇 관리
- v5: Anthropic API 직접 + tool use
- **v6: 자율 에이전트 + AI Router + Open WebUI Multi-AI**
