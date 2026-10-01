"""
인증 라우트 모듈 (auth.py)
- 이메일 회원가입, 로그인, 이메일 인증, 비밀번호 찾기 및 재설정
- Supabase Python 클라이언트 사용
- 에러/성공 메시지는 URL 파라미터로 전달하여 한국어로 알림 표시
"""

import os
import sys
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session
from supabase_auth.errors import AuthApiError
from app.services.supabase_client import get_supabase_client, get_admin_supabase_client
from app.services.auth_service import (
    login_required,
    admin_required,
    set_user_session,
    sign_up_user,
    sign_in_user,
    verify_email_otp,
    exchange_code,
    get_oauth_sign_in_url,
    send_password_reset_email,
    update_user_password,
    get_naver_auth_url,
    exchange_naver_code_for_token,
    get_naver_user_profile,
    get_or_create_social_user,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# 한국어 메시지 매핑 사전
ERROR_MESSAGES = {
    "email_not_confirmed": "이메일 인증이 완료되지 않았습니다. 수신된 이메일의 인증 링크를 먼저 확인해주세요.",
    "invalid_credentials": "이메일 또는 비밀번호가 올바르지 않습니다.",
    "missing_fields": "모든 필수 항목을 입력해주세요.",
    "password_mismatch": "비밀번호 확인이 일치하지 않습니다.",
    "weak_password": "비밀번호는 최소 6자 이상이어야 합니다.",
    "signup_failed": "회원가입 처리 중 오류가 발생했습니다. 다시 시도해주세요.",
    "user_already_exists": "이미 가입된 이메일 주소입니다. 로그인해주세요.",
    "confirm_failed": "유효하지 않거나 만료된 인증 링크입니다.",
    "oauth_failed": "소셜 로그인 연동 중 오류가 발생했습니다. 다시 시도해주세요.",
    "naver_config_missing": "네이버 로그인 설정(NAVER_CLIENT_ID)이 필요합니다.",
    "reset_request_failed": "비밀번호 재설정 메일 발송 중 오류가 발생했습니다.",
    "reset_failed": "비밀번호 재설정에 실패했습니다. 다시 시도해주세요.",
    "session_expired": "인증 정보가 만료되었습니다. 다시 시도해주세요.",
    "login_required": "해당 기능을 이용하려면 로그인이 필요합니다.",
    "profile_update_failed": "회원 정보 수정 중 오류가 발생했습니다. 다시 시도해주세요.",
    "current_password_mismatch": "현재 비밀번호가 일치하지 않습니다.",
    "same_as_current_password": "새로운 비밀번호가 현재 비밀번호와 동일합니다.",
    "password_change_failed": "비밀번호 변경 중 오류가 발생했습니다. 다시 시도해주세요.",
}

SUCCESS_MESSAGES = {
    "login_success": "로그인되었습니다. Young Style에 오신 것을 환영합니다!",
    "kakao_login_success": "카카오 계정으로 성공적으로 로그인되었습니다!",
    "google_login_success": "구글 계정으로 성공적으로 로그인되었습니다!",
    "naver_login_success": "네이버 계정으로 성공적으로 로그인되었습니다!",
    "social_login_success": "성공적으로 로그인되었습니다!",
    "signup_success": "회원가입이 완료되었습니다. 인증 이메일을 확인해주세요.",
    "reset_email_sent": "비밀번호 재설정 안내 메일이 발송되었습니다. 수신함을 확인해주세요.",
    "password_reset_success": "비밀번호가 성공적으로 변경되었습니다. 새로운 비밀번호로 로그인해주세요.",
    "logout_success": "로그아웃되었습니다.",
    "email_confirmed": "이메일 인증이 완료되었습니다.",
    "profile_updated": "회원 정보가 성공적으로 수정되었습니다.",
    "password_changed": "비밀번호가 변경되었습니다.",
}


def get_site_url() -> str:
    """사이트 기본 URL 반환 (환경 변수 우선, 없으면 현재 요청의 host_url 사용)"""
    env_site_url = os.getenv("SITE_URL")
    if env_site_url:
        return env_site_url.rstrip("/")
    if request:
        url = request.host_url.rstrip("/")
        # Azure / 리버스 프록시 헤더 확인하여 http를 https로 보정
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        if (forwarded_proto == "https" or "azurewebsites.net" in url) and url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        return url
    return "http://localhost:5000"


def get_flash_messages():
    """URL 파라미터에서 error 및 success 키를 추출하여 한국어 메시지로 변환"""
    error_key = request.args.get("error")
    success_key = request.args.get("success")

    error_msg = ERROR_MESSAGES.get(error_key, error_key if error_key else None)
    success_msg = SUCCESS_MESSAGES.get(success_key, success_key if success_key else None)

    return error_msg, success_msg


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    [1] GET/POST /auth/login - 로그인 폼 및 처리
    - 이메일 미인증 시 error=email_not_confirmed 로 리다이렉트
    - 로그인 성공 시 세션에 user_id, email, access_token 저장 후 메인(/) 또는 next 로 이동
    """
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        next_url = request.form.get("next") or url_for("main.index")

        if not email or not password:
            return redirect(url_for("auth.login", error="missing_fields", next=next_url))

        try:
            res = sign_in_user(email=email, password=password)
            user = res.get("user")
            auth_session = res.get("session")

            if not user:
                return redirect(url_for("auth.login", error="invalid_credentials", next=next_url))

            # Flask 세션에 사용자 정보 저장
            session["user_id"] = user.id
            session["user_email"] = user.email
            if auth_session:
                session["access_token"] = auth_session.access_token
                session["refresh_token"] = auth_session.refresh_token
            
            # 관리자 권한 확인
            set_user_session(user.id)

            # 별도 next 경로가 없으면 메인으로 이동하며 로그인 성공 메시지 전달
            if not request.form.get("next"):
                return redirect(url_for("main.index", success="login_success"))
            return redirect(next_url)

        except AuthApiError as e:
            # 이메일 미인증 상태 검출
            code = getattr(e, "code", "") or ""
            msg = str(e).lower()
            if code == "email_not_confirmed" or "email not confirmed" in msg:
                return redirect(url_for("auth.login", error="email_not_confirmed", next=next_url))
            return redirect(url_for("auth.login", error="invalid_credentials", next=next_url))
        except Exception as e:
            print(f"[에러] 로그인 예외 발생: {e}", file=sys.stderr)
            return redirect(url_for("auth.login", error="invalid_credentials", next=next_url))

    error_msg, success_msg = get_flash_messages()
    next_url = request.args.get("next", "")
    return render_template(
        "auth/login.html",
        error=error_msg,
        success=success_msg,
        next=next_url
    )


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """
    [2] GET/POST /auth/signup - 회원가입 폼 및 처리
    - 가입 성공 시 /auth/signup-complete 페이지 이동
    """
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        password_confirm = request.form.get("password_confirm", "").strip()

        if not email or not password or not password_confirm:
            return redirect(url_for("auth.signup", error="missing_fields"))

        if password != password_confirm:
            return redirect(url_for("auth.signup", error="password_mismatch"))

        if len(password) < 6:
            return redirect(url_for("auth.signup", error="weak_password"))

        confirm_redirect_url = f"{get_site_url()}/auth/confirm"

        try:
            sign_up_user(email=email, password=password, redirect_to=confirm_redirect_url)
            # 가입 성공 시 안내 페이지로 이동
            return redirect(url_for("auth.signup_complete", email=email))
        except AuthApiError as e:
            print(f"[에러] 회원가입 실패: {e}", file=sys.stderr)
            msg = (str(e.message) if hasattr(e, "message") else str(e)).lower()
            code = getattr(e, "code", "") or ""
            if "already registered" in msg or "already exists" in msg or code == "user_already_exists":
                return redirect(url_for("auth.signup", error="user_already_exists"))
            return redirect(url_for("auth.signup", error="signup_failed"))
        except Exception as e:
            print(f"[에러] 회원가입 예외 발생: {e}", file=sys.stderr)
            return redirect(url_for("auth.signup", error="signup_failed"))

    error_msg, success_msg = get_flash_messages()
    return render_template("auth/signup.html", error=error_msg, success=success_msg)


@auth_bp.route("/signup-complete")
def signup_complete():
    """
    [3] GET /auth/signup-complete - "인증 메일을 보냈습니다" 안내 페이지
    """
    email = request.args.get("email", "")
    return render_template("auth/signup_complete.html", email=email)


@auth_bp.route("/kakao")
def kakao_login():
    """
    [카카오 로그인 요청 라우트]
    Supabase Kakao OAuth 인증 URL을 생성하고 카카오 인가 페이지로 리다이렉트합니다.
    PKCE 검증을 위한 code_verifier를 Flask 세션에 안전하게 보관합니다.
    """
    redirect_url = f"{get_site_url()}/auth/callback"
    try:
        oauth_data = get_oauth_sign_in_url(provider="kakao", redirect_to=redirect_url)
        oauth_url = oauth_data.get("url")
        code_verifier = oauth_data.get("code_verifier")

        # 콜백 요청 시 PKCE 검증에 사용할 code_verifier 및 provider를 Flask session에 저장
        if code_verifier:
            session["oauth_code_verifier"] = code_verifier
        session["oauth_provider"] = "kakao"

        return redirect(oauth_url)
    except Exception as e:
        print(f"[에러] 카카오 OAuth URL 생성 실패: {e}", file=sys.stderr)
        return redirect(url_for("auth.login", error="oauth_failed"))


@auth_bp.route("/google")
def google_login():
    """
    [구글 로그인 요청 라우트]
    Supabase Google OAuth 인증 URL을 생성하고 구글 인가 페이지로 리다이렉트합니다.
    PKCE 검증을 위한 code_verifier를 Flask 세션에 안전하게 보관합니다.
    """
    redirect_url = f"{get_site_url()}/auth/callback"
    try:
        oauth_data = get_oauth_sign_in_url(provider="google", redirect_to=redirect_url)
        oauth_url = oauth_data.get("url")
        code_verifier = oauth_data.get("code_verifier")

        # 콜백 요청 시 PKCE 검증에 사용할 code_verifier 및 provider를 Flask session에 저장
        if code_verifier:
            session["oauth_code_verifier"] = code_verifier
        session["oauth_provider"] = "google"

        return redirect(oauth_url)
    except Exception as e:
        print(f"[에러] 구글 OAuth URL 생성 실패: {e}", file=sys.stderr)
        return redirect(url_for("auth.login", error="oauth_failed"))


@auth_bp.route("/naver")
def naver_login():
    """
    [네이버 로그인 요청 라우트]
    네이버 OAuth 2.0 인증 URL을 생성하고 네이버 인가 페이지로 리다이렉트합니다.
    """
    redirect_url = f"{get_site_url()}/auth/naver/callback"
    state = secrets.token_urlsafe(16)
    auth_url = get_naver_auth_url(redirect_uri=redirect_url, state=state)

    if not auth_url:
        print("[경고] NAVER_CLIENT_ID 환경 변수가 설정되지 않았습니다.", file=sys.stderr)
        return redirect(url_for("auth.login", error="naver_config_missing"))

    session["naver_oauth_state"] = state
    return redirect(auth_url)


@auth_bp.route("/naver/callback")
def naver_callback():
    """
    [네이버 OAuth 콜백 처리 라우트]
    네이버 로그인 완료 후 인가 코드를 받아 토큰 교환 및 사용자 프로필을 동기화합니다.
    """
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    error_description = request.args.get("error_description")

    saved_state = session.pop("naver_oauth_state", None)

    if error:
        print(f"[경고] 네이버 OAuth 콜백 에러: error={error}, desc={error_description}", file=sys.stderr)
        return redirect(url_for("auth.login", error=f"네이버 로그인 실패: {error_description or error}"))

    if not code:
        return redirect(url_for("auth.login", error="네이버 인가 코드가 누락되었습니다."))

    if not state or (saved_state and state != saved_state):
        print(f"[경고] 네이버 OAuth CSRF 불일치: state={state}, saved={saved_state}", file=sys.stderr)
        return redirect(url_for("auth.login", error="네이버 로그인 세션이 만료되었습니다. 다시 시도해주세요."))

    try:
        access_token = exchange_naver_code_for_token(code=code, state=state)
        if not access_token:
            return redirect(url_for("auth.login", error="네이버 액세스 토큰 발급에 실패했습니다. 키 설정을 확인해주세요."))

        profile = get_naver_user_profile(access_token)
        if not profile:
            return redirect(url_for("auth.login", error="네이버 프로필 정보를 조회할 수 없습니다."))

        naver_id = profile.get("id", "")
        email = profile.get("email") or f"naver_{naver_id[:12]}@naver.com"
        name = profile.get("name") or profile.get("nickname") or email.split("@")[0]
        avatar_url = profile.get("profile_image")

        user_id = get_or_create_social_user(
            email=email,
            name=name,
            avatar_url=avatar_url,
            provider="naver"
        )

        session["user_id"] = user_id
        session["user_email"] = email
        session["user_name"] = name
        
        # 관리자 권한 확인
        set_user_session(user_id)

        return redirect(url_for("main.index", success="naver_login_success"))

    except Exception as e:
        print(f"[에러] 네이버 로그인 처리 중 예외 발생: {e}", file=sys.stderr)
        return redirect(url_for("auth.login", error="oauth_failed"))


@auth_bp.route("/callback")
def oauth_callback():
    """
    [카카오/구글 OAuth 콜백 처리 라우트]
    OAuth 인증 완료 후 code 파라미터로 세션을 획득하고 로그인 처리합니다.
    """
    auth_code = request.args.get("code")
    error = request.args.get("error")
    error_desc = request.args.get("error_description") or ""

    if error or not auth_code:
        print(f"[경고] OAuth 콜백 에러 또는 인증 코드 누락: error={error}, desc={error_desc}", file=sys.stderr)
        err_msg = f"소셜 로그인 연동 실패: {error_desc or error or '인증 코드가 전달되지 않았습니다.'}"
        return redirect(url_for("auth.login", error=err_msg))

    # 세션에서 저장해둔 PKCE code_verifier 및 provider 꺼내기
    code_verifier = session.pop("oauth_code_verifier", None)
    provider = session.pop("oauth_provider", "")

    try:
        auth_res = exchange_code(auth_code, code_verifier=code_verifier)
        user = auth_res.get("user")
        auth_session = auth_res.get("session")

        if user:
            session["user_id"] = user.id
            session["user_email"] = user.email or (user.user_metadata.get("email") if hasattr(user, "user_metadata") and user.user_metadata else "")
            if auth_session:
                session["access_token"] = auth_session.access_token
                session["refresh_token"] = auth_session.refresh_token
            
            # 관리자 권한 확인
            set_user_session(user.id)

            # 프로바이더별 맞춤 성공 메시지 전달
            if provider == "google":
                success_key = "google_login_success"
            elif provider == "kakao":
                success_key = "kakao_login_success"
            else:
                success_key = "social_login_success"

            return redirect(url_for("main.index", success=success_key))

        return redirect(url_for("auth.login", error="사용자 정보를 가져올 수 없습니다. 다시 시도해주세요."))
    except Exception as e:
        print(f"[에러] OAuth 콜백 처리 중 오류: {e}", file=sys.stderr)
        err_str = str(e)
        if "PKCE" in err_str or "code_verifier" in err_str:
            err_msg = "인증 세션이 만료되었습니다. 다시 로그인 버튼을 눌러 시도해주세요."
        else:
            err_msg = f"소셜 로그인 처리 중 오류가 발생했습니다 ({err_str[:80]})."
        return redirect(url_for("auth.login", error=err_msg))


@auth_bp.route("/confirm")
def confirm():
    """
    [4] GET /auth/confirm - 이메일 인증 링크 클릭 처리
    - verify_otp 호출 → 성공 시 Flask session 저장 → /mypage
    - token_hash, token, code 등 파라미터 유연하게 처리
    """
    token_hash = request.args.get("token_hash")
    token = request.args.get("token")
    email = request.args.get("email")
    otp_type = request.args.get("type", "signup")
    auth_code = request.args.get("code")

    try:
        auth_res = None

        # 1. code(PKCE) 파라미터가 전달된 경우
        if auth_code:
            try:
                auth_res = exchange_code(auth_code)
            except Exception as e:
                print(f"[경고] code 교환 실패: {e}", file=sys.stderr)

        # 2. token_hash 또는 token 방식인 경우 verify_otp 호출
        if not auth_res and (token_hash or token):
            auth_res = verify_email_otp(
                token_hash=token_hash,
                token=token,
                email=email,
                otp_type=otp_type
            )

        if auth_res and auth_res.get("user"):
            user = auth_res["user"]
            auth_session = auth_res.get("session")

            # Flask session 저장
            session["user_id"] = user.id
            session["user_email"] = user.email
            if auth_session:
                session["access_token"] = auth_session.access_token
                session["refresh_token"] = auth_session.refresh_token
            
            # 관리자 권한 확인
            set_user_session(user.id)

            # 비밀번호 재설정 목적의 확인 링크인 경우
            if otp_type == "recovery":
                return redirect(url_for("auth.reset_password"))

            # 일반 회원가입 인증인 경우 /mypage 이동
            return redirect(url_for("auth.mypage", success="email_confirmed"))

        # 파라미터가 없거나 인증 응답 실패 시
        return redirect(url_for("auth.login", error="confirm_failed"))

    except Exception as e:
        print(f"[에러] 이메일 인증 실패: {e}", file=sys.stderr)
        return redirect(url_for("auth.login", error="confirm_failed"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """
    [5] GET/POST /auth/forgot-password - 비밀번호 재설정 메일 발송
    """
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            return redirect(url_for("auth.forgot_password", error="missing_fields"))

        redirect_url = f"{get_site_url()}/auth/confirm?type=recovery"

        try:
            send_password_reset_email(email=email, redirect_to=redirect_url)
            return redirect(url_for("auth.forgot_password", success="reset_email_sent"))
        except Exception as e:
            print(f"[에러] 비밀번호 재설정 이메일 전송 실패: {e}", file=sys.stderr)
            return redirect(url_for("auth.forgot_password", error="reset_request_failed"))

    error_msg, success_msg = get_flash_messages()
    return render_template("auth/forgot_password.html", error=error_msg, success=success_msg)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """
    [6] GET/POST /auth/reset-password - 새 비밀번호 설정
    """
    if request.method == "POST":
        new_password = request.form.get("password", "").strip()
        confirm_password = request.form.get("password_confirm", "").strip()

        if not new_password or not confirm_password:
            return redirect(url_for("auth.reset_password", error="missing_fields"))

        if new_password != confirm_password:
            return redirect(url_for("auth.reset_password", error="password_mismatch"))

        if len(new_password) < 6:
            return redirect(url_for("auth.reset_password", error="weak_password"))

        access_token = session.get("access_token")
        refresh_token = session.get("refresh_token")
        user_id = session.get("user_id")

        if not access_token and not user_id:
            return redirect(url_for("auth.login", error="session_expired"))

        try:
            update_user_password(
                new_password=new_password,
                access_token=access_token,
                refresh_token=refresh_token,
                user_id=user_id
            )
            # 비밀번호 변경 후 로그아웃 처리 또는 재로그인 유도
            session.clear()
            return redirect(url_for("auth.login", success="password_reset_success"))
        except Exception as e:
            print(f"[에러] 비밀번호 변경 실패: {e}", file=sys.stderr)
            return redirect(url_for("auth.reset_password", error="reset_failed"))

    error_msg, success_msg = get_flash_messages()
    return render_template("auth/reset_password.html", error=error_msg, success=success_msg)


@auth_bp.route("/logout")
def logout():
    """
    로그아웃 라우트
    - 세션 초기화 후 로그인 페이지 이동
    """
    session.clear()
    return redirect(url_for("auth.login", success="logout_success"))


@auth_bp.route("/mypage", methods=["GET", "POST"])
@login_required
def mypage():
    """
    마이페이지 라우트 (GET/POST /auth/mypage 또는 /mypage)
    - login_required 검증
    - GET: profiles 테이블에서 사용자 정보(이름, 이메일, 기본 배송지/주소, 전화번호 등) 조회하여 표시
    - POST: 내 정보(이름, 기본 배송지, 전화번호 등) 수정 처리
    """
    user_id = session.get("user_id")
    user_email = session.get("user_email")

    client = get_admin_supabase_client() or get_supabase_client()

    # POST: 내 정보 수정 처리
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        address = request.form.get("address", "").strip()

        try:
            if client and user_id:
                update_data = {
                    "full_name": full_name,
                    "phone_number": phone_number,
                }
                # profiles 테이블에 address 컬럼이 존재할 경우 대비, 없으면 메타데이터 보관
                try:
                    client.table("profiles").update({**update_data, "address": address}).eq("id", user_id).execute()
                except Exception:
                    client.table("profiles").update(update_data).eq("id", user_id).execute()

                # 세션에 이름 갱신
                if full_name:
                    session["user_name"] = full_name

            return redirect(url_for("auth.mypage", success="profile_updated"))
        except Exception as e:
            print(f"[에러] 프로필 수정 실패: {e}", file=sys.stderr)
            return redirect(url_for("auth.mypage", error="profile_update_failed"))

    # GET: 프로필 조회
    profile = {}
    is_email_user = False

    if client and user_id:
        try:
            res = client.table("profiles").select("*").eq("id", user_id).execute()
            if res.data and len(res.data) > 0:
                profile = res.data[0]
        except Exception as e:
            print(f"[경고] 프로필 조회 실패: {e}", file=sys.stderr)

        # 이메일/비밀번호 가입 여부 확인 (소셜 전용 계정 여부 판별)
        try:
            admin_client = get_admin_supabase_client()
            if admin_client:
                auth_user_resp = admin_client.auth.admin.get_user_by_id(user_id)
                auth_user = getattr(auth_user_resp, "user", None) or auth_user_resp
                if auth_user:
                    app_meta = getattr(auth_user, "app_metadata", {}) or {}
                    providers = app_meta.get("providers", [])
                    primary_prov = app_meta.get("provider", "")
                    identities = getattr(auth_user, "identities", []) or []
                    has_email_identity = any(getattr(i, "provider", "") == "email" for i in identities)
                    if "email" in providers or primary_prov == "email" or has_email_identity:
                        is_email_user = True
        except Exception as e:
            print(f"[경고] 사용자 인증 프로바이더 조회 실패: {e}", file=sys.stderr)
            is_email_user = not bool(session.get("oauth_provider"))

    error_msg, success_msg = get_flash_messages()
    return render_template(
        "auth/mypage.html",
        user_id=user_id,
        user_email=profile.get("email") or user_email,
        profile=profile,
        is_email_user=is_email_user,
        error=error_msg,
        success=success_msg
    )


@auth_bp.route("/mypage/change-password", methods=["POST"])
@login_required
def change_password():
    """
    [POST /mypage/change-password 또는 /auth/mypage/change-password]
    - 기존 비밀번호 검증 (Supabase 재로그인 방식)
    - 새 비밀번호 검증 (Day 4 가입 규칙과 동일: 필수, 일치, 6자 이상)
    - 새 비밀번호 != 기존 비밀번호 검증
    - Supabase update_user_by_id()를 통한 비밀번호 변경
    """
    user_id = session.get("user_id")
    user_email = session.get("user_email")

    current_password = request.form.get("current_password", "").strip()
    new_password = request.form.get("new_password", "").strip()
    new_password_confirm = request.form.get("new_password_confirm", "").strip()

    # 1. 필수 입력 필드 검증
    if not current_password or not new_password or not new_password_confirm:
        return redirect(url_for("auth.mypage", error="missing_fields"))

    # 2. 새 비밀번호와 기존 비밀번호 동일 여부 검증
    if current_password == new_password:
        return redirect(url_for("auth.mypage", error="same_as_current_password"))

    # 3. 새 비밀번호 확인 일치 여부
    if new_password != new_password_confirm:
        return redirect(url_for("auth.mypage", error="password_mismatch"))

    # 4. 새 비밀번호 길이 검증 (최소 6자 이상)
    if len(new_password) < 6:
        return redirect(url_for("auth.mypage", error="weak_password"))

    # 이메일 주소 확인
    admin = get_admin_supabase_client()
    if not user_email and admin and user_id:
        try:
            u_resp = admin.auth.admin.get_user_by_id(user_id)
            u = getattr(u_resp, "user", None) or u_resp
            if u and hasattr(u, "email") and u.email:
                user_email = u.email
        except Exception:
            pass

    if not user_email:
        return redirect(url_for("auth.mypage", error="session_expired"))

    # 5. 기존 비밀번호 검증 (Supabase 재로그인 시도)
    try:
        sign_in_user(email=user_email, password=current_password)
    except (AuthApiError, Exception) as e:
        print(f"[경고] 기존 비밀번호 검증 실패: {e}", file=sys.stderr)
        return redirect(url_for("auth.mypage", error="current_password_mismatch"))

    # 6. Supabase admin.update_user_by_id()로 새 비밀번호 반영
    try:
        if not admin:
            raise ValueError("Supabase 관리자 클라이언트를 초기화할 수 없습니다.")
        admin.auth.admin.update_user_by_id(user_id, {"password": new_password})
        return redirect(url_for("auth.mypage", success="password_changed"))
    except Exception as e:
        print(f"[에러] 비밀번호 변경 처리 오류: {e}", file=sys.stderr)
        return redirect(url_for("auth.mypage", error="password_change_failed"))
