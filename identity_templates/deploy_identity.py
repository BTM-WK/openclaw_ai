#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPENCLAW AI 삼국지 부대 — identity.md 원격 배포 스크립트
========================================================
사용법:
  python deploy_identity.py              # 자동 감지 모드
  python deploy_identity.py --bot 방통    # 수동 지정
  python deploy_identity.py --bot bangtong
  python deploy_identity.py --list       # 전체 봇 목록

이 스크립트는:
1. PC의 hostname과 openclaw 설치 경로를 감지
2. 해당 봇의 identity.md를 ~/.openclaw/workspace/identity.md에 배치
3. 기존 identity.md는 identity.md.bak으로 백업
"""

import os, sys, socket, shutil, argparse
from pathlib import Path
from datetime import datetime

BOT_MAP = {
    "bangtong": {"name": "WK방통", "role": "총괄 지휘 (리더봇)", "hostname_keys": ["yso-home", "yso-pc", "home-pc"], "file": "identity_bangtong.md"},
    "yubi": {"name": "WK유비", "role": "부사령관", "hostname_keys": ["wkmg", "office"], "file": "identity_yubi.md"},
    "gwanu": {"name": "WK관우", "role": "영업/제안", "hostname_keys": ["pc4", "four", "4ho"], "file": "identity_gwanu.md"},
    "gongmyeong": {"name": "WK공명", "role": "콘텐츠 제작", "hostname_keys": ["laptop", "note", "wkmg-note"], "file": "identity_gongmyeong.md"},
    "jangbi": {"name": "WK장비", "role": "관리지원/자동화", "hostname_keys": ["personal", "jangbi"], "file": "identity_jangbi.md"},
    "jaryong": {"name": "WK자룡", "role": "시장조사", "hostname_keys": ["pc10", "ten", "10ho"], "file": "identity_jaryong.md"},
    "jungdal": {"name": "WK중달", "role": "보고/리뷰", "hostname_keys": ["pc9", "nine", "9ho"], "file": "identity_jungdal.md"},
    "eight": {"name": "WK에이트", "role": "SNS/교육 모집", "hostname_keys": ["pc8", "eight", "8ho"], "file": "identity_eight.md"},
    "jason": {"name": "WK제이슨", "role": "미래성장/AI 실험", "hostname_keys": ["pc7", "seven", "7ho"], "file": "identity_jason.md"},
    "venus": {"name": "WK비너스", "role": "브랜드 마케팅", "hostname_keys": ["pc5", "five", "5ho"], "file": "identity_venus.md"},
    "helena": {"name": "WK헬레나", "role": "글로벌/수출", "hostname_keys": ["pc2", "two", "2ho"], "file": "identity_helena.md"},
}

KR_MAP = {"방통": "bangtong", "유비": "yubi", "관우": "gwanu", "공명": "gongmyeong", "장비": "jangbi", "자룡": "jaryong", "중달": "jungdal", "에이트": "eight", "제이슨": "jason", "비너스": "venus", "헬레나": "helena"}

def find_openclaw_workspace():
    home = Path.home()
    standard = home / ".openclaw" / "workspace"
    if standard.exists():
        return standard
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        alt = Path(userprofile) / ".openclaw" / "workspace"
        if alt.exists():
            return alt
    standard.mkdir(parents=True, exist_ok=True)
    return standard

def detect_bot(hostname):
    hn = hostname.lower()
    for bot_key, info in BOT_MAP.items():
        for key in info["hostname_keys"]:
            if key.lower() in hn:
                return bot_key
    return None

def deploy(bot_key, force=False):
    info = BOT_MAP[bot_key]
    script_dir = Path(__file__).parent.resolve()
    source = script_dir / info["file"]
    if not source.exists():
        print(f"[ERROR] identity 파일 없음: {source}")
        return False
    workspace = find_openclaw_workspace()
    target = workspace / "identity.md"
    if target.exists() and not force:
        backup = workspace / f"identity.md.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(target, backup)
        print(f"[BACKUP] 기존 파일 백업: {backup}")
    shutil.copy2(source, target)
    print(f"[SUCCESS] {info['name']} ({info['role']}) identity.md 배치 완료!")
    print(f"          위치: {target}")
    print(f"\n[NEXT] OpenClaw Gateway 재시작: openclaw gateway --port 18789")
    return True

def list_bots():
    print("\n=== OPENCLAW AI 삼국지 부대 봇 목록 ===\n")
    for key, info in BOT_MAP.items():
        print(f"  {key:15s} | {info['name']:10s} | {info['role']}")
    print(f"\n총 {len(BOT_MAP)}개 봇")
    print("\n사용법: python deploy_identity.py --bot <봇이름>")

def main():
    parser = argparse.ArgumentParser(description="OPENCLAW AI identity.md 배포")
    parser.add_argument("--bot", type=str, help="봇 이름 (한글 또는 영문)")
    parser.add_argument("--list", action="store_true", help="전체 봇 목록")
    parser.add_argument("--force", action="store_true", help="백업 없이 덮어쓰기")
    args = parser.parse_args()

    print("=" * 50)
    print("OPENCLAW AI 삼국지 부대 — identity.md 배포")
    print("=" * 50)

    if args.list:
        list_bots()
        return

    hostname = socket.gethostname()
    print(f"PC hostname: {hostname}")

    bot_key = None
    if args.bot:
        bot_input = args.bot.strip()
        if bot_input in KR_MAP:
            bot_key = KR_MAP[bot_input]
        elif bot_input.lower() in BOT_MAP:
            bot_key = bot_input.lower()
        else:
            print(f"[ERROR] 알 수 없는 봇: {bot_input}")
            list_bots()
            return
    else:
        bot_key = detect_bot(hostname)
        if not bot_key:
            print(f"[WARNING] hostname '{hostname}'으로 자동 감지 실패. --bot으로 수동 지정하세요.")
            list_bots()
            return

    info = BOT_MAP[bot_key]
    print(f"배포 대상: {info['name']} ({info['role']})")
    deploy(bot_key, force=args.force)

if __name__ == "__main__":
    main()
