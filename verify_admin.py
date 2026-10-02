from app.services.auth_service import get_admin_supabase_client

admin = get_admin_supabase_client()
email = "leeminwoo7878@gmail.com"

# 사용자 정보 확인
result = admin.table("profiles").select("id, email, role").eq("email", email).execute()

if result.data:
    user_id = result.data[0]["id"]
    print("✓ 관리자 계정 확인됨")
    print(f"  이메일: {email}")
    print(f"  역할: {result.data[0]['role']}")
    print()
    print("【관리자 접속 정보】")
    print(f"  이메일: {email}")
    print(f"  비밀번호: (회원가입 시 설정한 비밀번호)")
    print()
    print("비밀번호를 모르신다면, '비밀번호를 잊으셨나요?' 기능을 사용하세요!")
else:
    print("❌ 관리자 계정을 찾을 수 없습니다")
