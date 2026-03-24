# OPENCLAW AI 삼국지 부대 — identity.md 배포 가이드

## 개요
이 폴더에는 11개 봇 각각의 `identity.md` 파일이 들어있습니다.
각 파일을 해당 봇이 설치된 PC의 OpenClaw 작업 디렉토리에 배치하세요.

## 배치 경로
```
{사용자홈}\.openclaw\workspace\identity.md
```
예시:
- WK방통 (집PC): `C:\Users\yso\.openclaw\workspace\identity.md`
- WK유비 (회사PC): `C:\Users\{user}\.openclaw\workspace\identity.md`

## 파일 목록

| 파일명 | 봇 이름 | PC 위치 | 역할 |
|--------|---------|---------|------|
| `identity_bangtong.md` | WK방통 | 집PC (리더봇) | 총괄 지휘 |
| `identity_yubi.md` | WK유비 | 회사PC | 부사령관 |
| `identity_gwanu.md` | WK관우 | 4호기 | 영업/제안 |
| `identity_gongmyeong.md` | WK공명 | 회사노트북 | 콘텐츠 제작 |
| `identity_jangbi.md` | WK장비 | 개인노트북 | 관리지원/자동화 |
| `identity_jaryong.md` | WK자룡 | 10호기 | 시장조사 |
| `identity_jungdal.md` | WK중달 | 9호기 | 보고/리뷰 |
| `identity_eight.md` | WK에이트 | 8호기 | SNS/교육 모집 |
| `identity_jason.md` | WK제이슨 | 7호기 | 미래성장/AI 실험 |
| `identity_venus.md` | WK비너스 | 5호기 | 브랜드 마케팅 |
| `identity_helena.md` | WK헬레나 | 2호기 | 글로벌/수출 |

## 자동 배포 스크립트
`deploy_identity.py` 스크립트를 실행하면 해당 PC에 맞는 identity.md가 자동으로 배치됩니다.

```bash
python deploy_identity.py
```

## 수정 시 주의사항
- `## 절대 규칙` 섹션은 수정하지 마세요 (시스템 안정성 보호)
- 역할 범위나 판단 기준은 운영하면서 조정 가능
- 수정 후 반드시 Gateway 재시작 필요: `openclaw gateway --port 18789`
