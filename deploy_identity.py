#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPENCLAW AI 삼국지 부대 Identity 자동 배포 스크립트
각 PC에서 실행하면 해당 PC에 맞는 identity.md를 자동으로 배치합니다.

사용법:
python deploy_identity.py

작동 원리:
1. GitHub에서 최신 identity_templates를 pull
2. 현재 PC의 정보를 파악 (컴퓨터명, 경로 등)
3. 해당하는 identity 파일을 ~/.openclaw/workspace/identity.md로 복사
4. OpenClaw Gateway 재시작 (선택)
"""

import os
import sys
import socket
import shutil
import subprocess
import json
from pathlib import Path

# 봇별 PC 매핑 (컴퓨터명 기반)
BOT_MAPPING = {
    # 실제 컴퓨터명으로 수정 필요
    "DESKTOP-XXXXX": "bangtong",     # 집PC - WK방통
    "WKMG-DESKTOP": "yubi",          # 회사PC - WK유비  
    "LAPTOP-4": "gwanu",             # 4호기 - WK관우
    "WKMG-NOTEBOOK": "gongmyeong",   # 회사노트북 - WK공명
    "LAPTOP-PERSONAL": "jangbi",     # 개인노트북 - WK장비
    "DESKTOP-10": "jaryong",         # 10호기 - WK자룡
    "DESKTOP-9": "jungdal",          # 9호기 - WK중달
    "DESKTOP-8": "eight",            # 8호기 - WK에이트
    "DESKTOP-7": "jason",            # 7호기 - WK제이슨
    "DESKTOP-5": "venus",            # 5호기 - WK비너스
    "DESKTOP-2": "helena",           # 2호기 - WK헬레나
}

def get_computer_name():
    """현재 컴퓨터명을 가져온다"""
    return socket.gethostname()

def get_openclaw_workspace_path():
    """OpenClaw workspace/identity.md 경로를 찾는다"""
    user_home = Path.home()
    workspace_identity = user_home / '.openclaw' / 'workspace' / 'identity.md'
    return workspace_identity

def git_pull():
    """GitHub에서 최신 버전을 pull한다"""
    try:
        result = subprocess.run(['git', 'pull'], 
                               cwd=Path.cwd(), 
                               capture_output=True, 
                               text=True, 
                               timeout=30)
        if result.returncode == 0:
            print("✅ GitHub pull 성공")
            return True
        else:
            print(f"❌ Git pull 실패: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Git pull 오류: {e}")
        return False

def deploy_identity(bot_name):
    """해당 봇의 identity.md를 배치한다"""
    source_file = Path(f"identity_templates/identity_{bot_name}.md")
    target_file = get_openclaw_workspace_path()
    
    if not source_file.exists():
        print(f"❌ 소스 파일을 찾을 수 없음: {source_file}")
        return False
    
    # 백업 생성
    if target_file.exists():
        backup_file = target_file.with_suffix('.md.backup')
        shutil.copy2(target_file, backup_file)
        print(f"📋 기존 파일 백업: {backup_file}")
    
    # 타겟 디렉토리 생성
    target_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 파일 복사
    try:
        shutil.copy2(source_file, target_file)
        print(f"✅ Identity 배치 완료: {target_file}")
        return True
    except Exception as e:
        print(f"❌ 파일 복사 실패: {e}")
        return False

def restart_openclaw():
    """OpenClaw Gateway를 재시작한다"""
    try:
        # Windows 환경에서 openclaw gateway 재시작
        print("🔄 OpenClaw Gateway 재시작 중...")
        # 기존 프로세스 정리
        subprocess.run(['taskkill', '/F', '/IM', 'node.exe'], 
                      capture_output=True, timeout=10)
        
        # 잠시 대기
        import time
        time.sleep(3)
        
        # 새로 시작 (백그라운드)
        subprocess.Popen(['openclaw', 'gateway', '--port', '18789'], 
                        shell=True)
        print("✅ OpenClaw Gateway 재시작 완료")
        return True
    except Exception as e:
        print(f"❌ Gateway 재시작 실패: {e}")
        print("수동으로 'openclaw gateway --port 18789' 실행해주세요")
        return False

def main():
    print("🚀 OPENCLAW AI 삼국지 부대 Identity 배포 시작")
    print("=" * 50)
    
    # 1. 현재 PC 정보 확인
    computer_name = get_computer_name()
    print(f"💻 현재 PC: {computer_name}")
    
    # 2. 봇 이름 매핑
    bot_name = BOT_MAPPING.get(computer_name)
    if not bot_name:
        print(f"❌ 등록되지 않은 PC입니다: {computer_name}")
        print("다음 중 해당하는 봇 이름을 선택하세요:")
        for i, (pc, bot) in enumerate(BOT_MAPPING.items(), 1):
            print(f"  {i}. {bot}")
        
        try:
            choice = int(input("번호 입력: ")) - 1
            bot_name = list(BOT_MAPPING.values())[choice]
        except (ValueError, IndexError):
            print("❌ 잘못된 선택입니다.")
            sys.exit(1)
    
    print(f"🤖 배포 대상 봇: WK{bot_name}")
    
    # 3. Git pull 실행
    if not git_pull():
        print("⚠️  Git pull 실패했지만 계속 진행...")
    
    # 4. Identity 파일 배치
    if deploy_identity(bot_name):
        print("✅ Identity 배치 성공")
    else:
        print("❌ Identity 배치 실패")
        sys.exit(1)
    
    # 5. Gateway 재시작 여부 확인
    restart_choice = input("OpenClaw Gateway를 재시작할까요? (y/N): ").lower()
    if restart_choice in ['y', 'yes']:
        restart_openclaw()
    else:
        print("ℹ️  수동으로 Gateway를 재시작해주세요: openclaw gateway --port 18789")
    
    print("=" * 50)
    print("🎉 Identity 배포 완료!")
    print("텔레그램에서 봇이 새로운 정체성으로 응답하는지 확인해보세요.")

if __name__ == "__main__":
    main()
