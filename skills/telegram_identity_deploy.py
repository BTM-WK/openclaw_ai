"""
OpenClaw Skill: Identity 원격 배포

텔레그램 명령:
- "identity 업데이트"
- "아이덴티티 배포" 
- "identity deploy"
- "정체성 업데이트"

기능:
1. GitHub에서 최신 identity 파일 pull
2. 현재 PC에 맞는 identity.md 자동 배치
3. 배포 결과 텔레그램으로 보고
"""

import subprocess
import sys
import os
import socket
import shutil
import asyncio
from pathlib import Path

class TelegramIdentityDeployer:
    def __init__(self):
        self.bot_mapping = {
            # PC별 봇 매핑 (실제 컴퓨터명으로 업데이트 필요)
            socket.gethostname(): "bangtong",  # 현재 PC 자동 매핑
            "DESKTOP-WKMG": "yubi",
            "NOTEBOOK-4": "gwanu", 
            "LAPTOP-WKMG": "gongmyeong",
            "PERSONAL-PC": "jangbi",
            "DESKTOP-10": "jaryong",
            "DESKTOP-9": "jungdal", 
            "DESKTOP-8": "eight",
            "DESKTOP-7": "jason",
            "DESKTOP-5": "venus",
            "DESKTOP-2": "helena",
        }
        
    async def git_pull(self):
        """GitHub pull 실행"""
        try:
            result = await asyncio.create_subprocess_exec(
                'git', 'pull',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd()
            )
            
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=60)
            
            if result.returncode == 0:
                output = stdout.decode('utf-8', errors='ignore')
                if "Already up to date" in output:
                    return True, "이미 최신 버전입니다"
                elif "files changed" in output:
                    return True, "새로운 업데이트 적용됨"
                else:
                    return True, "Pull 완료"
            else:
                error = stderr.decode('utf-8', errors='ignore')
                return False, f"Git pull 실패: {error}"
                
        except asyncio.TimeoutError:
            return False, "Git pull 타임아웃"
        except Exception as e:
            return False, f"Git 오류: {str(e)}"
            
    def determine_bot(self):
        """현재 PC의 봇 이름 결정"""
        computer_name = socket.gethostname()
        bot_name = self.bot_mapping.get(computer_name)
        
        if bot_name:
            return bot_name, f"PC '{computer_name}' → WK{bot_name}"
        else:
            # 매핑되지 않은 PC의 경우 기본값
            return "bangtong", f"알 수 없는 PC '{computer_name}' → WK방통(기본값)"
            
    def deploy_identity_file(self, bot_name):
        """Identity 파일 배치"""
        try:
            # 소스 파일 경로
            source_file = Path(f"identity_templates/identity_{bot_name}.md")
            if not source_file.exists():
                return False, f"Identity 파일 없음: identity_{bot_name}.md"
                
            # 타겟 경로
            user_home = Path.home()
            workspace_path = user_home / '.openclaw' / 'workspace'
            identity_file = workspace_path / 'identity.md'
            
            # 디렉토리 생성
            workspace_path.mkdir(parents=True, exist_ok=True)
            
            # 백업 (기존 파일이 있는 경우)
            if identity_file.exists():
                backup_file = identity_file.with_suffix('.md.backup')
                shutil.copy2(identity_file, backup_file)
                
            # 파일 복사
            shutil.copy2(source_file, identity_file)
            
            return True, f"배치 완료: {identity_file}"
            
        except Exception as e:
            return False, f"배치 실패: {str(e)}"
            
    async def execute_deployment(self):
        """전체 배포 과정 실행"""
        results = []
        
        # 1. 봇 결정
        bot_name, mapping_info = self.determine_bot()
        results.append(f"🤖 {mapping_info}")
        
        # 2. GitHub pull
        results.append("📥 GitHub 업데이트 확인 중...")
        pull_success, pull_msg = await self.git_pull()
        
        if pull_success:
            results.append(f"✅ {pull_msg}")
        else:
            results.append(f"⚠️ {pull_msg} (로컬 파일로 진행)")
            
        # 3. Identity 배치
        results.append("📁 Identity 파일 배치 중...")
        deploy_success, deploy_msg = self.deploy_identity_file(bot_name)
        
        if deploy_success:
            results.append(f"✅ {deploy_msg}")
        else:
            results.append(f"❌ {deploy_msg}")
            return False, "\n".join(results)
            
        # 4. 완료 메시지
        results.append("")
        results.append(f"🎉 WK{bot_name} Identity 배포 완료!")
        results.append("💡 Gateway 재시작 권장: openclaw gateway --port 18789")
        
        return True, "\n".join(results)

# OpenClaw 스킬 메인 함수
async def handle_identity_command(message, context):
    """
    텔레그램에서 identity 관련 명령 처리
    
    지원 명령:
    - identity 업데이트, 배포, deploy
    - 아이덴티티 업데이트, 배포  
    - 정체성 업데이트
    - id 업데이트 (축약형)
    """
    
    text = message.text.lower().strip()
    
    # 명령어 패턴 매칭
    identity_keywords = [
        'identity', '아이덴티티', '정체성', 'id업데이트', 'id 업데이트'
    ]
    
    action_keywords = [
        '업데이트', '배포', 'deploy', 'update', '적용'
    ]
    
    # identity 키워드가 포함되고, 액션 키워드도 포함된 경우
    has_identity = any(keyword in text for keyword in identity_keywords)
    has_action = any(keyword in text for keyword in action_keywords)
    
    if has_identity and has_action:
        # 배포 시작 메시지
        await context.reply("🚀 Identity 자동 배포를 시작합니다...")
        
        try:
            deployer = TelegramIdentityDeployer()
            success, result_message = await deployer.execute_deployment()
            
            # 결과 전송
            await context.reply(result_message)
            
            if success:
                await context.reply("텔레그램에서 봇의 새로운 응답을 확인해보세요! 🎭")
            else:
                await context.reply("문제가 발생한 경우 수동 배포를 시도해주세요.")
                
        except Exception as e:
            await context.reply(f"❌ 배포 중 오류 발생:\n{str(e)}")
            await context.reply("수동 배포 명령:\npython deploy_identity_v2.py --auto")
            
        return True
    
    # 단순 "identity" 또는 "아이덴티티" 질문인 경우
    elif any(keyword in text for keyword in identity_keywords) and len(text) < 20:
        await context.reply(
            "🤖 Identity 관련 명령어:\n\n"
            "• identity 업데이트 - 자동 배포\n"
            "• 아이덴티티 배포 - 자동 배포\n" 
            "• identity deploy - 자동 배포\n\n"
            "현재 이 PC의 identity가 궁금하다면:\n"
            "• 내 정체성은?\n"
            "• 나는 누구야?"
        )
        return True
        
    return False

# 봇 정체성 질문 처리
async def handle_identity_question(message, context):
    """
    봇 정체성에 대한 질문 처리
    "나는 누구야?", "내 정체성은?", "네 역할은?" 등
    """
    
    text = message.text.lower().strip()
    
    identity_questions = [
        '나는 누구', '내 정체성', '네 정체성', '네 역할',
        '누구야', '누구세요', '어떤 봇', '무슨 봇'
    ]
    
    if any(question in text for question in identity_questions):
        try:
            # 현재 identity.md 파일 읽기
            user_home = Path.home()
            identity_file = user_home / '.openclaw' / 'workspace' / 'identity.md'
            
            if identity_file.exists():
                with open(identity_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 기본 정보 섹션 추출
                lines = content.split('\n')
                basic_info = []
                in_basic_section = False
                
                for line in lines:
                    if '## 기본 정보' in line:
                        in_basic_section = True
                        continue
                    elif line.startswith('## ') and in_basic_section:
                        break
                    elif in_basic_section and line.strip():
                        basic_info.append(line)
                        
                if basic_info:
                    info_text = '\n'.join(basic_info[:6])  # 처음 6줄만
                    await context.reply(f"🤖 현재 나의 정체성:\n\n{info_text}")
                else:
                    await context.reply("현재 identity 파일에서 기본 정보를 찾을 수 없습니다.")
                    
            else:
                await context.reply("❌ Identity 파일이 없습니다. 'identity 업데이트' 명령을 실행해주세요.")
                
        except Exception as e:
            await context.reply(f"❌ Identity 정보 조회 실패: {str(e)}")
            
        return True
        
    return False

# 통합 핸들러 (OpenClaw에서 호출)
async def handle_message(message, context):
    """메시지 통합 처리"""
    
    # Identity 배포 명령 처리
    if await handle_identity_command(message, context):
        return True
        
    # Identity 질문 처리  
    if await handle_identity_question(message, context):
        return True
        
    return False
