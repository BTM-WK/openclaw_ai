#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPENCLAW AI 삼국지 부대 Identity 원격 배포 스크립트 v2.0

주요 기능:
1. GitHub 자동 pull로 최신 identity 파일 동기화
2. PC별 자동 봇 매핑 (컴퓨터명 기반 또는 수동 선택)
3. OpenClaw workspace에 자동 배치
4. Gateway 재시작 옵션

사용법:
python deploy_identity_v2.py [--auto] [--restart]

작동 과정:
1. 현재 PC 정보 확인 → 봇 매핑
2. GitHub에서 최신 identity 파일 pull
3. 해당 봇의 identity.md를 ~/.openclaw/workspace/에 배치
4. 선택적으로 OpenClaw Gateway 재시작
"""

import os
import sys
import socket
import shutil
import subprocess
import json
import time
import argparse
from pathlib import Path

def setup_console():
    """Windows 콘솔 UTF-8 설정"""
    if sys.platform == "win32":
        try:
            os.system("chcp 65001 > nul 2>&1")
        except:
            pass

class IdentityDeployer:
    def __init__(self):
        setup_console()
        
        # 11개 봇 매핑 - 실제 PC명에 맞게 업데이트 필요
        self.BOT_MAPPING = {
            # 확인된 PC (현재 집PC)
            socket.gethostname(): "bangtong",  # 현재 PC는 방통으로 자동 매핑
            
            # 나머지 PC들 - 실제 컴퓨터명으로 수정 필요
            "DESKTOP-WKMG": "yubi",           # 회사PC - WK유비
            "NOTEBOOK-4": "gwanu",            # 4호기 - WK관우  
            "LAPTOP-WKMG": "gongmyeong",      # 회사노트북 - WK공명
            "PERSONAL-PC": "jangbi",          # 개인노트북 - WK장비
            "DESKTOP-10": "jaryong",          # 10호기 - WK자룡
            "DESKTOP-9": "jungdal",           # 9호기 - WK중달
            "DESKTOP-8": "eight",             # 8호기 - WK에이트
            "DESKTOP-7": "jason",             # 7호기 - WK제이슨
            "DESKTOP-5": "venus",             # 5호기 - WK비너스
            "DESKTOP-2": "helena",            # 2호기 - WK헬레나
        }
        
        self.BOT_LIST = [
            "bangtong", "yubi", "gwanu", "gongmyeong", 
            "jangbi", "jaryong", "jungdal", "eight", 
            "jason", "venus", "helena"
        ]
        
    def log(self, message, level="INFO"):
        """로그 출력"""
        symbols = {
            "INFO": "→",
            "SUCCESS": "✓", 
            "ERROR": "×",
            "WARNING": "!",
            "QUESTION": "?"
        }
        symbol = symbols.get(level, "→")
        print(f"{symbol} {message}")
        
    def get_computer_info(self):
        """현재 PC 정보 수집"""
        computer_name = socket.gethostname()
        user_name = os.environ.get('USERNAME', 'unknown')
        return computer_name, user_name
        
    def determine_bot(self, auto_mode=False):
        """봇 이름 결정"""
        computer_name, user_name = self.get_computer_info()
        self.log(f"현재 PC: {computer_name} (사용자: {user_name})")
        
        # 자동 매핑 확인
        bot_name = self.BOT_MAPPING.get(computer_name)
        
        if bot_name and auto_mode:
            self.log(f"자동 매핑: WK{bot_name}", "SUCCESS")
            return bot_name
            
        if bot_name:
            self.log(f"매핑된 봇: WK{bot_name}")
            confirm = input(f"{self.BOT_MAPPING[computer_name]} 맞습니까? (Y/n): ").lower()
            if confirm in ['', 'y', 'yes']:
                return bot_name
                
        # 수동 선택
        self.log("수동 봇 선택:", "QUESTION")
        for i, bot in enumerate(self.BOT_LIST, 1):
            print(f"  {i:2d}. WK{bot}")
            
        while True:
            try:
                choice = input("\n번호 선택 (1-11): ").strip()
                if not choice:
                    continue
                idx = int(choice) - 1
                if 0 <= idx < len(self.BOT_LIST):
                    selected_bot = self.BOT_LIST[idx]
                    self.log(f"선택된 봇: WK{selected_bot}", "SUCCESS")
                    return selected_bot
                else:
                    self.log("1-11 사이 번호를 입력하세요", "ERROR")
            except ValueError:
                self.log("숫자를 입력하세요", "ERROR")
                
    def git_pull(self):
        """GitHub에서 최신 버전 pull"""
        self.log("GitHub에서 최신 업데이트 확인...")
        
        try:
            result = subprocess.run(
                ['git', 'pull'],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.log("GitHub pull 완료", "SUCCESS")
                # pull 결과 요약 출력
                if "Already up to date" in result.stdout:
                    self.log("이미 최신 버전입니다")
                elif "files changed" in result.stdout:
                    self.log("새로운 업데이트가 적용되었습니다")
                return True
            else:
                self.log(f"Git pull 실패: {result.stderr.strip()}", "ERROR")
                return False
                
        except FileNotFoundError:
            self.log("Git이 설치되지 않았거나 PATH에 없습니다", "ERROR")
            return False
        except subprocess.TimeoutExpired:
            self.log("Git pull 타임아웃 (60초)", "ERROR") 
            return False
        except Exception as e:
            self.log(f"Git pull 오류: {str(e)}", "ERROR")
            return False
            
    def get_openclaw_paths(self):
        """OpenClaw 경로들 반환"""
        user_home = Path.home()
        workspace_path = user_home / '.openclaw' / 'workspace'
        identity_file = workspace_path / 'identity.md'
        return workspace_path, identity_file
        
    def deploy_identity(self, bot_name):
        """Identity 파일 배치"""
        self.log(f"WK{bot_name} identity 배치 시작...")
        
        # 소스 파일 확인
        source_file = Path(f"identity_templates/identity_{bot_name}.md")
        if not source_file.exists():
            self.log(f"Identity 파일이 없습니다: {source_file}", "ERROR")
            return False
            
        # 타겟 경로 준비
        workspace_path, identity_file = self.get_openclaw_paths()
        
        # 디렉토리 생성
        try:
            workspace_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log(f"디렉토리 생성 실패: {e}", "ERROR")
            return False
            
        # 백업 생성 (기존 파일이 있는 경우)
        if identity_file.exists():
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = identity_file.with_suffix(f'.md.backup_{timestamp}')
            try:
                shutil.copy2(identity_file, backup_file)
                self.log(f"기존 파일 백업: {backup_file.name}")
            except Exception as e:
                self.log(f"백업 실패: {e}", "WARNING")
                
        # Identity 파일 복사
        try:
            shutil.copy2(source_file, identity_file)
            self.log(f"Identity 배치 완료: {identity_file}", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"파일 복사 실패: {e}", "ERROR")
            return False
            
    def restart_openclaw_gateway(self):
        """OpenClaw Gateway 재시작"""
        self.log("OpenClaw Gateway 재시작 중...")
        
        try:
            # 기존 Node.js 프로세스 종료
            subprocess.run(
                ['taskkill', '/F', '/IM', 'node.exe'],
                capture_output=True,
                timeout=10
            )
            self.log("기존 Gateway 프로세스 종료")
            
            # 대기
            time.sleep(3)
            
            # OpenClaw Gateway 시작
            if sys.platform == "win32":
                # Windows: 백그라운드에서 실행
                subprocess.Popen(
                    ['openclaw', 'gateway', '--port', '18789'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Linux/macOS
                subprocess.Popen(
                    ['openclaw', 'gateway', '--port', '18789'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
            self.log("OpenClaw Gateway 재시작 완료", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Gateway 재시작 실패: {e}", "ERROR")
            self.log("수동 재시작: openclaw gateway --port 18789", "WARNING")
            return False
            
    def run(self, auto_mode=False, auto_restart=False):
        """메인 실행 함수"""
        print("=" * 60)
        print("🤖 OPENCLAW AI 삼국지 부대 Identity 원격 배포 v2.0")
        print("=" * 60)
        
        # 1. 봇 결정
        bot_name = self.determine_bot(auto_mode)
        
        # 2. GitHub pull
        pull_success = self.git_pull()
        if not pull_success:
            self.log("GitHub pull 실패 - 로컬 파일로 진행", "WARNING")
            
        # 3. Identity 배치
        if not self.deploy_identity(bot_name):
            self.log("배포 실패", "ERROR")
            return False
            
        # 4. Gateway 재시작
        if auto_restart:
            self.restart_openclaw_gateway()
        else:
            restart_choice = input("\nOpenClaw Gateway를 재시작하시겠습니까? (y/N): ").lower()
            if restart_choice in ['y', 'yes']:
                self.restart_openclaw_gateway()
            else:
                self.log("수동 재시작 필요: openclaw gateway --port 18789", "WARNING")
                
        print("=" * 60)
        self.log(f"WK{bot_name} Identity 배포 완료!", "SUCCESS") 
        self.log("텔레그램에서 봇의 새로운 응답을 확인해보세요!")
        print("=" * 60)
        
        return True

def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(description='OPENCLAW Identity 배포')
    parser.add_argument('--auto', action='store_true', 
                       help='자동 모드 (PC 매핑 자동 감지)')
    parser.add_argument('--restart', action='store_true',
                       help='배포 후 자동으로 Gateway 재시작')
    
    args = parser.parse_args()
    
    deployer = IdentityDeployer()
    success = deployer.run(auto_mode=args.auto, auto_restart=args.restart)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
