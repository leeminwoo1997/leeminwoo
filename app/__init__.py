import os
from flask import Flask
from dotenv import load_dotenv

# .env 파일에서 환경 변수 불러오기
load_dotenv()

def create_app():
    """
    [앱 팩토리 함수]
    Flask 애플리케이션 인스턴스를 생성하고 환경 설정 및 블루프린트를 등록합니다.
    초보자도 이해하기 쉬운 구조로 설계되었습니다.
    """
    app = Flask(__name__)

    # 기본 설정 적용
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default-dev-secret-key")

    # 블루프린트(라우트 모듈) 등록
    from app.routes.main import main_bp
    from app.routes.inquiry import inquiry_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(inquiry_bp)

    return app
