import os
import sys
from flask import Blueprint, render_template
from dotenv import load_dotenv
from supabase import create_client, Client

# .env 파일 로드
load_dotenv()

# 'main' 블루프린트 생성
main_bp = Blueprint("main", __name__)

# Supabase 클라이언트 초기화 함수
def get_supabase_client() -> Client | None:
    """
    .env의 SUPABASE_URL 및 SUPABASE_ANON_KEY를 읽어 Supabase 클라이언트를 생성합니다.
    설정이 누락되었거나 오류 발생 시 None을 반환합니다.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_key:
        print("[경고] SUPABASE_URL 또는 SUPABASE_ANON_KEY 환경 변수가 설정되지 않았습니다.", file=sys.stderr)
        return None

    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"[에러] Supabase 클라이언트 초기화 실패: {e}", file=sys.stderr)
        return None

@main_bp.route("/")
def index():
    """
    메인 페이지 라우트
    - Supabase products 테이블에서 is_active=true AND is_featured=true인 상품 최대 6개 조회
    - 대표 썸네일 이미지 및 포맷팅된 가격('19,900원') 가공 후 index.html에 전달
    - 연결 또는 조회 실패 시 에러 로그를 출력하고 빈 리스트로 안전하게 대체
    """
    formatted_products = []

    try:
        supabase = get_supabase_client()
        if supabase:
            # 1차 시도: is_featured 컬럼이 존재하는 경우
            try:
                response = (
                    supabase.table("products")
                    .select("id, name, description, price, discount_rate, is_active, is_featured, product_images(image_url, is_primary)")
                    .eq("is_active", True)
                    .eq("is_featured", True)
                    .limit(6)
                    .execute()
                )
            except Exception as query_err:
                # is_featured 컬럼이 DB에 없는 경우 is_active 조건만으로 폴백(Fallback) 조회
                if "is_featured" in str(query_err):
                    print("[안내] DB에 is_featured 컬럼이 없어 is_active 상품으로 대체 조회합니다.", file=sys.stderr)
                    response = (
                        supabase.table("products")
                        .select("id, name, description, price, discount_rate, is_active, product_images(image_url, is_primary)")
                        .eq("is_active", True)
                        .limit(6)
                        .execute()
                    )
                else:
                    raise query_err

            for item in response.data:
                # 썸네일 이미지 추출 (대표 이미지 우선, 없으면 첫 번째 이미지, 둘 다 없으면 기본 플레이스홀더)
                images = item.get("product_images", [])
                thumbnail_url = None
                if images:
                    primary_imgs = [img["image_url"] for img in images if img.get("is_primary")]
                    thumbnail_url = primary_imgs[0] if primary_imgs else images[0]["image_url"]

                if not thumbnail_url:
                    thumbnail_url = f"https://picsum.photos/seed/product-{item.get('id')}/600/750"

                # 가격 포맷팅 ('19,900원' 형태)
                raw_price = item.get("price") or 0
                formatted_price = f"{int(raw_price):,}원"

                formatted_products.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description", ""),
                    "price": formatted_price,
                    "thumbnail_url": thumbnail_url
                })
        else:
            print("[알림] Supabase 클라이언트가 없어 빈 상품 목록을 반환합니다.", file=sys.stderr)

    except Exception as e:
        # Supabase 연결 및 쿼리 실패 시 앱이 중단되지 않도록 에러 로깅 후 빈 리스트 유지
        print(f"[에러] Supabase 상품 데이터 조회 중 오류 발생: {e}", file=sys.stderr)
        formatted_products = []

    return render_template("index.html", products=formatted_products)

