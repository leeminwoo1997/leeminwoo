from app import create_app
import os
from dotenv import load_dotenv

load_dotenv()

# Flask 앱 컨텍스트 내에서 실행
app = create_app()

with app.app_context():
    from app.services.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    
    email = "leeminwoo7878@gmail.com"
    new_password = "Admin@123456"
    
    # Supabase Auth 사용자 인증 업데이트
    try:
        # 먼저 사용자 조회
        users = supabase.auth.admin_list_users()
        
        # 해당 이메일의 사용자 찾기
        target_user = None
        for user in users.users:
            if user.email == email:
                target_user = user
                break
        
        if target_user:
            # 비밀번호 업데이트
            updated_user = supabase.auth.admin_update_user_by_id(
                target_user.id,
                {"password": new_password}
            )
            print(f"✓ 비밀번호 업데이트 완료!")
            print(f"\n【관리자 로그인 정보】")
            print(f"  이메일: {email}")
            print(f"  비밀번호: {new_password}")
        else:
            print(f"❌ 사용자를 찾을 수 없습니다: {email}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print(f"\n대안: 직접 비밀번호 리셋 페이지에서 이메일 인증 진행")
        print(f"  http://127.0.0.1:5000/auth/forgot-password")
