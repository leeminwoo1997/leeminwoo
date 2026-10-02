from app.services.supabase_client import get_supabase_client

supabase = get_supabase_client()

# 관리자 계정 확인
admins = supabase.table("profiles").select("id, email, role").eq("role", "admin").execute()
print("✓ 관리자 계정:")
if admins.data:
    for admin in admins.data:
        print(f"  - ID: {admin['id']}")
        print(f"    이메일: {admin['email']}")
        print(f"    역할: {admin['role']}")
else:
    print("  ❌ 관리자 계정이 없습니다.")
    print("\n모든 사용자 목록:")
    users = supabase.table("profiles").select("id, email, role").limit(10).execute()
    for user in users.data:
        print(f"  - {user['email']} (역할: {user['role']})")
