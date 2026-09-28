"""
VIBE FASHION 애플리케이션 진입점 (Entry Point)
앱 팩토리 함수(create_app)를 호출하여 서버를 구동합니다.
"""
from app import create_app

# 애플리케이션 생성
app = create_app()

if __name__ == "__main__":
    # 로컬 개발 서버 실행 (포트 5000, 디버그 모드 활성화)
    print("==================================================")
    print(" VIBE FASHION 쇼핑몰 서버가 시작되었습니다.")
    print(" 브라우저 접속 주소: http://127.0.0.1:5000")
    print("==================================================")
    app.run(host="127.0.0.1", port=5000, debug=True)
