"""
Supabase 클라이언트 공통 모듈 (supabase_client.py)
- 애플리케이션 전역에서 사용되는 Supabase 클라이언트 초기화 로직 단일화
- 일반(Anon/Service) 클라이언트 및 관리자(Service Role) 클라이언트 제공
"""

import os
import sys
from typing import Optional
from supabase import create_client, Client


def get_supabase_client() -> Optional[Client]:
    """
    일반적인 데이터 조회/인증/스토리지 작업용 Supabase 클라이언트를 반환합니다.
    SUPABASE_ANON_KEY 또는 SUPABASE_SERVICE_KEY를 사용합니다.
    """
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not supabase_key:
        print("[경고] SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다.", file=sys.stderr)
        return None

    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"[에러] Supabase 클라이언트 초기화 실패: {e}", file=sys.stderr)
        return None


def get_admin_supabase_client() -> Optional[Client]:
    """
    관리자 권한의 Supabase 클라이언트를 반환합니다.
    SUPABASE_SERVICE_KEY가 필요합니다.
    """
    supabase_url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        return None

    try:
        return create_client(supabase_url, service_key)
    except Exception as e:
        print(f"[에러] Supabase 관리자 클라이언트 초기화 실패: {e}", file=sys.stderr)
        return None
