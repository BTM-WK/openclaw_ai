#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPENCLAW AI 삼국지 부대 Identity 자동 배포 스크립트

원격 배포 방법:
1. GitHub에서 최신 identity_templates를 pull
2. 현재 PC 정보를 파악하여 해당 봇의 identity.md 배치
3. OpenClaw Gateway 재시작

사용법: python deploy_identity.py
"""

import os
import sys
import socket
import shutil
import subprocess
import json
from pathlib import Path

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == "win32":
    os.system("chcp 65001 >nul")
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 봇별 PC 매핑 (실제 컴퓨터명으로 업데이트 필요)
BOT_MAPPING = {
    # 현재 확인된 PC
    "": "bangtong",                    # 집PC - WK방통 (현재 PC)
    
    # 추정 매핑 (실제 컴퓨터명으로 수정 필요)
    "WKMG-DESKTOP": "yubi",           # 회사PC - WK유비  
    "DESKTOP-4": "gwanu",             # 4호기 - WK관우
    "WKMG-NOTEBOOK": "gongmyeong",    # 회사노트북 - WK공명
    "PERSONAL-LAPTOP": "jangbi",      # 개인노트북 - WK장비
    "DESKTOP-10": "jaryong",          # 10호기 - WK자룡
    "DESKTOP-9": "jungdal",           # 9호기 - WK중달
    "DESKTOP-8": "eight",             # 8호기 - WK에이트
    "DESKTOP-7": "jason",             # 7호기 - WK제이슨
    "DESKTOP-5": "venus",             # 5호기 - WK비너스
    "DESKTOP-2": "helena",            # 2호기 - WK헬레나
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
            print("✓ GitHub pull 성공")
            return True
        else:
            print(f"× Git pull 실패: {result.stderr}")
            return False
    except Exception as e:
        print(f"× Git pull 오류: {e}")
        return False

def deploy_identity(bot_name):
    """해당 봇의 identity.md를 배치한다"""
    source_file = Path(f"identity_templates/identity_{bot_name}.md")
    target_file = get_openclaw_workspace_path()
    
    if not source_file.exists():
        print(f"× 소스 파일을 찾을 수 없음: {source_file}")
        return False
    
    # 백업 생성
    if target_file.exists():
        backup_file = target_file.with_suffix('.md.backup')
        shutil.copy2(target_file, backup_file)
        print(f"→ 기존 파일 백업: {backup_file}")
    
    # 타겟 디렉토리 생성
    target_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 파일 복사
    try:
        shutil.copy2(source_file, target_file)
        print(f"✓ Identity 배치 완료: {target_file}")
        return True
    except Exception as e:
        print(f"× 파일 복사 실패: {e}")
        return False

def restart_openclaw():
    """OpenClaw Gateway를 재시작한다"""
    try:
        print("→ OpenClaw Gateway 재시작 중...")
        # Windows에서 기존 프로세스 정리
        subprocess.run(['taskkill', '/F', '/IM', 'node.exe'], 
                      capture_output=True, timeout=10)
        
        import time
        time.sleep(3)
        
        # 새로 시작 (백그라운드)
        subprocess.Popen(['openclaw', 'gateway', '--port', '18789'], 
                        shell=True)
        print("✓ OpenClaw Gateway 재시작 완료")
        return True
    except Exception as e:
        print(f"× Gateway 재시작 실패: {e}")
        print("→ 수동 재시작: openclaw gateway --port 18789")
        return False

def main():
    print("OPENCLAW AI 삼국지 부대 Identity 배포")
    print("=" * 50)
    
    # 1. 현재 PC 정보 확인
    computer_name = get_computer_name()
    print(f"현재 PC: {computer_name}")
    
    # 2. 봇 이름 매핑
    bot_name = BOT_MAPPING.get(computer_name)
    if not bot_name:
        print(f"× 등록되지 않은 PC: {computer_name}")
        print("\n봇 선택:")
        bot_list = list(BOT_MAPPING.values())
        for i, bot in enumerate(bot_list, 1):
            print(f"  {i}. WK{bot}")
        
        try:
            choice = int(input("\n번호 입력: ")) - 1
            bot_name = bot_list[choice]
        except (ValueError, IndexError):
            print("× 잘못된 선택")
            sys.exit(1)
    
    print(f"배포 대상: WK{bot_name}")
    
    # 3. Git pull 실행
    print("\nGitHub에서 최신 업데이트 확인...")
    if not git_pull():
        print("→ Git pull 실패 - 로컬 파일로 진행")
    
    # 4. Identity 파일 배치
    print(f"\n{bot_name} identity 배치 중...")
    if deploy_identity(bot_name):
        print("✓ Identity 배치 완료")
    else:
        print("× 배치 실패")
        sys.exit(1)
    
    # 5. Gateway 재시작 선택
    restart_choice = input("\nGateway 재시작? (y/N): ").lower()
    if restart_choice in ['y', 'yes']:
        restart_openclaw()
    else:
        print("→ 수동 재시작 필요: openclaw gateway --port 18789")
    
    print("=" * 50)
    print("배포 완료! 텔레그램에서 봇 응답을 확인하세요.")

if __name__ == "__main__":
    main()
