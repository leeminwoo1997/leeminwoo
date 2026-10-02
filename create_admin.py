from app.services.auth_service import get_admin_supabase_client

# 관리자 클라이언트로 시도
admin_supabase = get_admin_supabase_client()

result = admin_supabase.table("profiles").update({"role": "admin"}).eq("email", "leeminwoo7878@gmail.com").execute()

if result.data:
    print("✓ 관리자 계정 생성 완료!")
    print(f"  이메일: leeminwoo7878@gmail.com")
    print(f"  역할: {result.data[0]['role']}")
else:
    print("❌ 업데이트 실패")
    print(f"에러: {result}")
