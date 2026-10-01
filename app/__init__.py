import os
from flask import Flask, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from app.services.cart_service import get_cart_summary
from app.routes.main import main_bp
from app.routes.inquiry import inquiry_bp
from app.routes.cart import cart_bp
from app.routes.auth import auth_bp

# .env 파일에서 환경 변수 불러오기
load_dotenv()

def create_app():
    """
    [앱 팩토리 함수]
    Flask 애플리케이션 인스턴스를 생성하고 환경 설정 및 블루프린트를 등록합니다.
    """
    app = Flask(__name__)

    # 기본 설정 적용
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default-dev-secret-key")

    # 소셜 로그인(OAuth) 외부 리다이렉트 후에도 세션 쿠키가 유지되도록 SameSite=Lax 설정
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False  # HTTPS 환경에서는 ProxyFix와 함께 브라우저가 처리, 유연한 동작 지원

    # Azure App Service / 리버스 프록시 뒤에서 HTTPS 헤더(X-Forwarded-Proto, Host) 정상 인식
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # 블루프린트(라우트 모듈) 등록
    app.register_blueprint(main_bp)
    app.register_blueprint(inquiry_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(auth_bp)

    # /mypage 및 /mypage/change-password 최상위 경로도 auth 모듈로 편리하게 직접 연결
    @app.route("/mypage", methods=["GET", "POST"])
    def top_mypage():
        from app.routes.auth import mypage
        return mypage()

    @app.route("/mypage/change-password", methods=["POST"])
    def top_change_password():
        from app.routes.auth import change_password
        return change_password()

    # 모든 템플릿에서 장바구니 요약 정보에 접근할 수 있도록 컨텍스트 프로세서 등록
    @app.context_processor
    def inject_cart():
        return {"cart_summary": get_cart_summary()}

    return app
