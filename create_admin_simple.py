from app import create_app
from app.services.supabase_client import get_supabase_client
from app.services.auth_service import get_admin_supabase_client

# Flask 앱 생성
app = create_app()

# Supabase 클라이언트
supabase = get_supabase_client()
admin_supabase = get_admin_supabase_client()

# 새로운 관리자 테스트 계정
email = "admin@youngstyle.com"
password = "Admin123456!"

try:
    # Supabase Auth에 사용자 생성 (REST API 사용)
    import requests
    import json
    
    auth_url = f"https://pihshyiiwhrgqjmmffwe.supabase.co/auth/v1/admin/users"
    headers = {
        "Authorization": f"Bearer {supabase.auth.get_session()}",
        "Content-Type": "application/json"
    }
    
    # 대신 Supabase의 signUp 사용
    result = supabase.auth.sign_up({
        "email": email,
        "password": password
    })
    
    if result.user:
        print(f"✓ 관리자 계정 생성 완료!")
        print(f"  이메일: {email}")
        print(f"  비밀번호: {password}")
        print(f"  ID: {result.user.id}")
        
        # profiles 테이블 업데이트
        admin_supabase.table("profiles").update({
            "role": "admin"
        }).eq("id", result.user.id).execute()
        
        print(f"  ✓ 관리자 권한 설정됨")
    else:
        print(f"❌ 사용자 생성 실패: {result}")
        
except Exception as e:
    print(f"❌ 오류: {e}")
    print("\n대안: 기존 계정의 비밀번호를 사용하세요")
    print(f"  이메일: leeminwoo7878@gmail.com")
    print(f"  (회원가입 시 설정한 비밀번호)")
