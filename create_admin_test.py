import os
from dotenv import load_dotenv
from supabase import create_client

# .env 파일 로드
load_dotenv()

# Supabase Admin API 사용
url = os.getenv("SUPABASE_URL")
admin_key = os.getenv("SUPABASE_SERVICE_KEY")

admin_client = create_client(url, admin_key)

# 새로운 관리자 테스트 계정 생성
email = "admin@youngstyle.com"
password = "Admin123456!"

try:
    # Supabase Auth에 사용자 생성
    user = admin_client.auth.admin_create_user({
        "email": email,
        "password": password,
        "email_confirm": True
    })
    
    print(f"✓ 관리자 계정 생성 완료!")
    print(f"  이메일: {email}")
    print(f"  비밀번호: {password}")
    print(f"  ID: {user.user.id}")
    
    # profiles 테이블에 관리자 역할 추가
    from app.services.auth_service import get_admin_supabase_client
    db_admin = get_admin_supabase_client()
    
    # 프로필이 이미 존재하는지 확인
    existing = db_admin.table("profiles").select("*").eq("id", user.user.id).execute()
    
    if not existing.data:
        # 새 프로필 생성
        db_admin.table("profiles").insert({
            "id": user.user.id,
            "email": email,
            "role": "admin"
        }).execute()
        print(f"  ✓ 프로필 생성됨")
    else:
        # 기존 프로필 업데이트
        db_admin.table("profiles").update({"role": "admin"}).eq("id", user.user.id).execute()
        print(f"  ✓ 프로필 업데이트됨")
        
except Exception as e:
    print(f"❌ 오류: {e}")
