from app import create_app
from app.services.auth_service import get_admin_supabase_client
import os

app = create_app()

# 관리자 클라이언트로 비밀번호 업데이트 시도
admin_client = get_admin_supabase_client()

email = "leeminwoo7878@gmail.com"
new_password = "Admin123456!"

try:
    # 사용자 ID 찾기
    result = admin_client.table("profiles").select("id").eq("email", email).execute()
    
    if result.data:
        user_id = result.data[0]['id']
        print(f"✓ 사용자 찾음: {user_id}")
        
        # Supabase Auth Client를 사용해서 비밀번호 업데이트
        try:
            # auth_client를 이용해 비밀번호 업데이트
            admin_client.auth.admin_update_user_by_id(user_id, {
                "password": new_password
            })
            print(f"✓ 비밀번호 업데이트 완료!")
            print(f"\n로그인 정보:")
            print(f"  이메일: {email}")
            print(f"  비밀번호: {new_password}")
        except AttributeError:
            print("❌ auth 메서드를 찾을 수 없습니다.")
            print("대신 다른 방법으로 시도합니다...")
        
    else:
        print(f"❌ 사용자를 찾을 수 없습니다: {email}")
        
except Exception as e:
    print(f"❌ 오류: {e}")
