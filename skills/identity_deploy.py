"""
OpenClaw Skill: Identity 배포 자동화

텔레그램에서 "identity 업데이트" 명령으로 실행 가능한 스킬
"""

import subprocess
import sys
import os
from pathlib import Path

async def identity_update(context):
    """Identity 자동 배포 실행"""
    
    try:
        # deploy_identity.py 스크립트 실행
        script_path = Path.cwd() / "deploy_identity.py"
        
        if not script_path.exists():
            return {
                "success": False,
                "message": "❌ deploy_identity.py 스크립트를 찾을 수 없습니다."
            }
        
        # Python 스크립트 실행
        result = subprocess.run([
            sys.executable, 
            str(script_path)
        ], 
        capture_output=True, 
        text=True, 
        timeout=60,
        input="n\n"  # 재시작 질문에 기본값(N) 응답
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": "✅ Identity 업데이트 완료",
                "output": result.stdout
            }
        else:
            return {
                "success": False,
                "message": "❌ Identity 업데이트 실패",
                "error": result.stderr
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ 오류: {str(e)}"
        }

# OpenClaw 스킬 메인 함수
async def handle_identity_update(message, context):
    """텔레그램 명령 처리: identity 업데이트"""
    
    text = message.text.lower()
    
    if any(keyword in text for keyword in [
        "identity", "아이덴티티", "정체성", "업데이트", "배포"
    ]):
        
        await context.reply("🚀 Identity 자동 배포 시작...")
        
        result = await identity_update(context)
        
        await context.reply(result["message"])
        
        return True
    
    return False
