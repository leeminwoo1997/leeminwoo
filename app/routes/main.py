import sys
from flask import Blueprint, render_template, request, jsonify, abort
from app.services.supabase_client import get_supabase_client
from app.routes.auth import get_flash_messages

# 'main' 블루프린트 생성
main_bp = Blueprint("main", __name__)

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
                    .order("created_at", desc=False)
                    .limit(24)
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
                        .order("created_at", desc=False)
                        .limit(24)
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
                    # 이미지가 등록되지 않은 경우 기본 의류 플레이스홀더 이미지 적용
                    thumbnail_url = "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?auto=format&fit=crop&w=600&q=80"

                # 가격 포맷팅 ('19,900원' 형태)
                raw_price = int(item.get("price") or 0)
                formatted_price = f"{raw_price:,}원"

                formatted_products.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description", ""),
                    "price": formatted_price,
                    "price_num": raw_price,
                    "thumbnail_url": thumbnail_url
                })
        else:
            print("[알림] Supabase 클라이언트가 없어 빈 상품 목록을 반환합니다.", file=sys.stderr)

    except Exception as e:
        # Supabase 연결 및 쿼리 실패 시 앱이 중단되지 않도록 에러 로깅 후 빈 리스트 유지
        print(f"[에러] Supabase 상품 데이터 조회 중 오류 발생: {e}", file=sys.stderr)
        formatted_products = []

    error_msg, success_msg = get_flash_messages()
    return render_template(
        "index.html",
        products=formatted_products,
        error=error_msg,
        success=success_msg
    )


@main_bp.route("/products/<product_id>")
def product_detail(product_id: str):
    """
    [상품 상세 페이지 라우트]
    - Supabase에서 product_id로 상품 상세 정보 및 이미지 조회
    - 상품 이미지, 이름, 가격(정가/할인가/할인율), 설명 가공
    - product_options 테이블에서 해당 상품의 유효한 색상(color) 목록을 중복 없이(DISTINCT) 조회
    - templates/product_detail.html 렌더링
    """
    supabase = get_supabase_client()
    if not supabase:
        abort(500, description="데이터베이스 연결에 실패했습니다.")

    try:
        # 1. 상품 정보 및 이미지 조회
        p_res = (
            supabase.table("products")
            .select("id, name, slug, description, price, discount_rate, is_active, product_images(image_url, is_primary, display_order)")
            .eq("id", product_id)
            .execute()
        )

        if not p_res.data or len(p_res.data) == 0:
            abort(404, description="존재하지 않거나 삭제된 상품입니다.")

        product = p_res.data[0]

        # 이미지 목록 정렬 및 썸네일 선정
        images = product.get("product_images", []) or []
        images.sort(key=lambda img: (not img.get("is_primary", False), img.get("display_order", 0)))
        main_image_url = images[0]["image_url"] if images else "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?auto=format&fit=crop&w=800&q=80"

        # 가격 및 할인 계산
        original_price = int(product.get("price") or 0)
        discount_rate = float(product.get("discount_rate") or 0.0)

        if discount_rate > 0:
            discounted_price = int(round(original_price * (1 - discount_rate / 100.0)))
        else:
            discounted_price = original_price

        # 2. product_options 테이블에서 해당 상품의 색상 목록 조회 (NULL 제외 및 중복 제거)
        opt_res = (
            supabase.table("product_options")
            .select("color")
            .eq("product_id", product_id)
            .not_.is_("color", "null")
            .execute()
        )

        # Python set을 이용해 중복 제거 및 정렬
        seen_colors = []
        for r in (opt_res.data or []):
            c = r.get("color")
            if c and c not in seen_colors:
                seen_colors.append(c)

        product_detail_data = {
            "id": product["id"],
            "name": product["name"],
            "description": product.get("description") or "상세 설명이 등록되지 않은 상품입니다.",
            "original_price": original_price,
            "original_price_str": f"{original_price:,}원",
            "discount_rate": int(round(discount_rate)),
            "discounted_price": discounted_price,
            "discounted_price_str": f"{discounted_price:,}원",
            "has_discount": discount_rate > 0 and discounted_price < original_price,
            "main_image_url": main_image_url,
            "images": [img["image_url"] for img in images] if images else [main_image_url],
            "colors": seen_colors
        }

        error_msg, success_msg = get_flash_messages()
        return render_template(
            "product_detail.html",
            product=product_detail_data,
            error=error_msg,
            success=success_msg
        )

    except Exception as e:
        print(f"[에러] 상품 상세 조회 오류: {e}", file=sys.stderr)
        abort(404, description="상품 정보를 불러오는 중 오류가 발생했습니다.")


@main_bp.route("/api/products/<product_id>/sizes")
@main_bp.route("/products/<product_id>/options")
def get_product_sizes_by_color(product_id: str):
    """
    [상품 색상 선택 시 호출되는 사이즈 및 재고 조회 API]
    - URL: GET /api/products/<product_id>/sizes?color=<선택한 색상>
    - product_options 테이블에서 product_id + color로 필터링
    - size, stock 정보를 담은 JSON 배열 반환
      예: [{"size": "S", "stock": 3}, {"size": "M", "stock": 0}]
    """
    color = request.args.get("color", "").strip()
    if not color:
        return jsonify([])

    supabase = get_supabase_client()
    if not supabase:
        return jsonify({"error": "데이터베이스 연결에 실패했습니다."}), 500

    try:
        # 해당 상품 + 색상에 매칭되는 옵션 조회
        res = (
            supabase.table("product_options")
            .select("id, size, stock, stock_quantity, additional_price")
            .eq("product_id", product_id)
            .eq("color", color)
            .not_.is_("size", "null")
            .execute()
        )

        size_list = []
        # 사이즈 순서 정렬 기준 (XS, S, M, L, XL, XXL, FREE 등)
        size_priority = {"XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6, "FREE": 7}

        for row in (res.data or []):
            stock = row.get("stock")
            if stock is None:
                stock = row.get("stock_quantity") or 0
            stock = max(0, int(stock))

            size_name = row.get("size")
            size_list.append({
                "option_id": row.get("id"),
                "size": size_name,
                "stock": stock
            })

        # 사이즈 정렬 (S -> M -> L 순서)
        size_list.sort(key=lambda s: size_priority.get(str(s["size"]).upper(), 99))

        return jsonify(size_list)

    except Exception as e:
        print(f"[에러] 색상별 사이즈 조회 실패: {e}", file=sys.stderr)
        return jsonify({"error": "옵션을 조회할 수 없습니다."}), 500

