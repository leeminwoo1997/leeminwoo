import os
from flask import Flask, redirect, url_for
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

    # 블루프린트(라우트 모듈) 등록
    app.register_blueprint(main_bp)
    app.register_blueprint(inquiry_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(auth_bp)

    # /mypage 최상위 경로도 auth.mypage로 편리하게 접근할 수 있도록 라우트 추가
    @app.route("/mypage")
    def top_mypage():
        return redirect(url_for("auth.mypage"))

    # 모든 템플릿에서 장바구니 요약 정보에 접근할 수 있도록 컨텍스트 프로세서 등록
    @app.context_processor
    def inject_cart():
        return {"cart_summary": get_cart_summary()}

    return app
