"""
인증 서비스 (auth_service.py)
- Supabase Python 클라이언트를 활용한 사용자 인증 로직 모듈
- 회원가입, 로그인, OTP 검증, 비밀번호 재설정 이메일 발송, 비밀번호 변경 기능 제공
- 한국어 주석 및 Supabase 클라이언트 표준 API 사용
"""

import os
import sys
import uuid
import secrets
import urllib.parse
from functools import wraps
from typing import Any, Dict, Optional
import httpx
from flask import session, redirect, url_for, request
from supabase import Client
from app.services.supabase_client import get_supabase_client, get_admin_supabase_client


def get_auth_supabase_client() -> Client:
    """
    인증 전용 Supabase 클라이언트를 반환합니다.
    """
    client = get_supabase_client()
    if not client:
        raise ValueError("SUPABASE_URL 및 키 환경 변수가 설정되지 않았습니다.")
    return client


def login_required(f):
    """
    로그인 필수 데코레이터
    - Flask session에 'user_id'가 존재하는지 확인
    - 없으면 /auth/login 페이지로 리다이렉트하며 에러 파라미터(error=login_required) 전달
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            # 미로그인 상태일 때 로그인 페이지로 이동
            return redirect(url_for("auth.login", error="login_required", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def sign_up_user(email: str, password: str, redirect_to: Optional[str] = None) -> Dict[str, Any]:
    """
    [Supabase Auth] 이메일 회원가입 요청
    """
    supabase = get_auth_supabase_client()
    options: Dict[str, Any] = {}
    if redirect_to:
        options["email_redirect_to"] = redirect_to

    response = supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": options
    })
    return {
        "user": response.user,
        "session": response.session
    }


def sign_in_user(email: str, password: str) -> Dict[str, Any]:
    """
    [Supabase Auth] 이메일/비밀번호 로그인 처리
    - 이메일 미인증 상태일 경우 AuthApiError 발생 (code: 'email_not_confirmed')
    """
    supabase = get_auth_supabase_client()
    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    return {
        "user": response.user,
        "session": response.session
    }


def verify_email_otp(token_hash: Optional[str] = None, token: Optional[str] = None,
                     email: Optional[str] = None, otp_type: str = "signup") -> Dict[str, Any]:
    """
    [Supabase Auth] 이메일 인증/확인 처리 (verify_otp)
    - token_hash 방식 또는 email + token 방식 지원
    - otp_type: 'signup' (기본 회원가입 인증), 'recovery' (비밀번호 재설정) 등
    """
    supabase = get_auth_supabase_client()
    params: Dict[str, Any] = {"type": otp_type}

    if token_hash:
        params["token_hash"] = token_hash
    elif token and email:
        params["token"] = token
        params["email"] = email
    elif token:
        params["token_hash"] = token
    else:
        raise ValueError("인증에 필요한 토큰 정보가 부족합니다.")

    response = supabase.auth.verify_otp(params)
    return {
        "user": response.user,
        "session": response.session
    }


def exchange_code(code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
    """
    [Supabase Auth] PKCE auth_code 교환 처리
    - Flask session 등에 저장된 code_verifier가 있으면 함께 전달하여 멀티 워커/인스턴스 환경에서도 안전하게 세션 교환
    """
    supabase = get_auth_supabase_client()
    params: Dict[str, Any] = {"auth_code": code}
    if code_verifier:
        params["code_verifier"] = code_verifier
    response = supabase.auth.exchange_code_for_session(params)
    return {
        "user": response.user,
        "session": response.session
    }


def get_oauth_sign_in_url(provider: str, redirect_to: str) -> Dict[str, str]:
    """
    [Supabase Auth] 소셜 로그인(Kakao 등) 인증 URL 생성 및 code_verifier 반환
    """
    supabase = get_auth_supabase_client()
    res = supabase.auth.sign_in_with_oauth({
        "provider": provider,
        "options": {
            "redirect_to": redirect_to
        }
    })
    # supabase-py가 생성하여 메모리 스토리지에 저장한 code_verifier 추출
    verifier = supabase.auth._storage.get_item(f"{supabase.auth._storage_key}-code-verifier")
    return {
        "url": res.url,
        "code_verifier": verifier or ""
    }


def send_password_reset_email(email: str, redirect_to: str) -> None:
    """
    [Supabase Auth] 비밀번호 재설정 이메일 발송
    """
    supabase = get_auth_supabase_client()
    supabase.auth.reset_password_for_email(
        email=email,
        options={"redirect_to": redirect_to}
    )


def update_user_password(new_password: str, access_token: Optional[str] = None,
                         refresh_token: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    [Supabase Auth] 새 비밀번호 설정
    1. access_token 및 refresh_token이 있으면 세션을 복원 후 update_user 호출
    2. access_token만 있으면 JWT 헤더를 통한 직접 요청 또는 admin 클라이언트로 업데이트
    3. user_id가 주어지고 서비스 롤 키가 있으면 admin.update_user_by_id로 최종 안전 업데이트
    """
    supabase = get_auth_supabase_client()

    # 방법 1: 세션 복원 후 update_user
    if access_token and refresh_token:
        try:
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            response = supabase.auth.update_user({"password": new_password})
            return {"user": response.user}
        except Exception as e:
            print(f"[경고] set_session을 통한 비밀번호 변경 실패, 대체 수단 시도: {e}", file=sys.stderr)

    # 방법 2: access_token 직접 사용
    if access_token:
        try:
            supabase.auth._request(
                "PUT",
                "user",
                body={"password": new_password},
                jwt=access_token
            )
            return {"success": True}
        except Exception as e:
            print(f"[경고] JWT를 통한 직접 비밀번호 변경 실패, 대체 수단 시도: {e}", file=sys.stderr)

    # 방법 3: Admin 서비스 롤 키를 통한 업데이트
    if user_id:
        admin_client = get_admin_supabase_client()
        if admin_client:
            res = admin_client.auth.admin.update_user_by_id(user_id, {"password": new_password})
            return {"user": res.user}

    raise ValueError("비밀번호 변경을 수행할 수 있는 유효한 인증 정보가 없습니다.")


# ==============================================================================
# 네이버(Naver) OAuth 2.0 소셜 로그인 헬퍼 함수
# ==============================================================================

def get_naver_auth_url(redirect_uri: str, state: str) -> Optional[str]:
    """
    네이버 로그인 인가 URL 생성
    - NAVER_CLIENT_ID가 설정되어 있어야 함
    """
    client_id = os.getenv("NAVER_CLIENT_ID", "").strip()
    if not client_id:
        return None

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state
    }
    return f"https://nid.naver.com/oauth2.0/authorize?{urllib.parse.urlencode(params)}"


def exchange_naver_code_for_token(code: str, state: str) -> Optional[str]:
    """
    네이버 인가 코드를 access_token으로 교환
    """
    client_id = os.getenv("NAVER_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None

    url = "https://nid.naver.com/oauth2.0/token"
    params = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "state": state
    }
    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        data = resp.json()
        return data.get("access_token")
    except Exception as e:
        print(f"[에러] 네이버 토큰 발급 실패: {e}", file=sys.stderr)
        return None


def get_naver_user_profile(access_token: str) -> Optional[Dict[str, Any]]:
    """
    네이버 access_token을 사용하여 사용자 프로필 정보 조회
    """
    url = "https://openapi.naver.com/v1/nid/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10.0)
        data = resp.json()
        if data.get("resultcode") == "00":
            return data.get("response")
        print(f"[경고] 네이버 회원 정보 조회 실패 응답: {data}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[에러] 네이버 회원 정보 조회 요청 예외: {e}", file=sys.stderr)
        return None


def get_or_create_social_user(email: str, name: str, avatar_url: Optional[str] = None, provider: str = "naver") -> str:
    """
    소셜 계정(네이버 등) 사용자 정보를 바탕으로 Supabase 사용자를 조회하거나 생성
    - 이미 존재하는 경우 user_id 반환
    - 없는 경우 관리자 권한으로 신규 사용자 및 프로필 생성
    """
    admin = get_admin_supabase_client()
    if admin:
        # 1. 기존 가입 사용자 확인
        try:
            users = admin.auth.admin.list_users()
            for u in users:
                if u.email and u.email.lower() == email.lower():
                    return u.id
        except Exception as e:
            print(f"[경고] Supabase list_users 조회 실패: {e}", file=sys.stderr)

        # 2. 신규 사용자 생성
        try:
            res = admin.auth.admin.create_user({
                "email": email,
                "email_confirm": True,
                "password": secrets.token_urlsafe(24),
                "user_metadata": {
                    "full_name": name,
                    "name": name,
                    "avatar_url": avatar_url,
                    "provider": provider
                }
            })
            if res and res.user:
                return res.user.id
        except Exception as e:
            print(f"[경고] Supabase create_user 실패: {e}", file=sys.stderr)
            # 동시성 등으로 이미 생성되었을 경우 다시 조회
            try:
                users = admin.auth.admin.list_users()
                for u in users:
                    if u.email and u.email.lower() == email.lower():
                        return u.id
            except Exception:
                pass

    # Admin 클라이언트 미설정 시 안전한 고유 식별자(UUIDv5) 폴백
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{provider}:{email}"))
