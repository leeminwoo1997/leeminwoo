"""
인증 서비스 (auth_service.py)
- Supabase Python 클라이언트를 활용한 사용자 인증 로직 모듈
- 회원가입, 로그인, OTP 검증, 비밀번호 재설정 이메일 발송, 비밀번호 변경 기능 제공
- 한국어 주석 및 Supabase 클라이언트 표준 API 사용
"""

import sys
from functools import wraps
from typing import Any, Dict, Optional
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


def exchange_code(code: str) -> Dict[str, Any]:
    """
    [Supabase Auth] PKCE auth_code 교환 처리
    """
    supabase = get_auth_supabase_client()
    response = supabase.auth.exchange_code_for_session({"auth_code": code})
    return {
        "user": response.user,
        "session": response.session
    }


def get_oauth_sign_in_url(provider: str, redirect_to: str) -> str:
    """
    [Supabase Auth] 소셜 로그인(Kakao 등) 인증 URL 생성
    """
    supabase = get_auth_supabase_client()
    res = supabase.auth.sign_in_with_oauth({
        "provider": provider,
        "options": {
            "redirect_to": redirect_to
        }
    })
    return res.url


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
