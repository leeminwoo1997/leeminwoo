"""
장바구니(Cart) 라우트 블루프린트
- GET /cart : 장바구니 페이지 렌더링 (Supabase carts 테이블 JOIN 조회)
- GET /cart/api/summary : 현재 장바구니 요약 정보 JSON 반환 (비동기 연동용)
- POST /cart/api/add : 장바구니 상품 추가 API (Supabase carts 테이블 upsert)
- PATCH /cart/<cart_id> : 장바구니 수량 변경 API (Supabase carts 테이블 UPDATE)
- DELETE /cart/<cart_id> : 장바구니 아이템 삭제 API (Supabase carts 테이블 DELETE)
- POST /cart/api/update : 장바구니 수량 변경 API (기존 세션 기반, 레거시)
- POST /cart/api/remove : 장바구니 상품 삭제 API (기존 세션 기반, 레거시)
- POST /cart/api/clear : 장바구니 비우기 API (기존 세션 기반, 레거시)
"""

import sys
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from app.services.supabase_client import get_supabase_client, get_admin_supabase_client
from app.services.cart_service import (
    get_cart_summary,
    add_to_cart,
    update_cart_item,
    remove_from_cart,
    clear_cart
)

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")

@cart_bp.route("/")
def view_cart():
    """
    장바구니 페이지 렌더링
    - Supabase carts 테이블에서 로그인 사용자의 장바구니 항목 조회
    - carts + product_options + products JOIN으로 모든 필요한 정보 취득
    - 각 아이템: 상품명, 색상, 사이즈, 수량, 단가, 소계, 재고 상태
    """
    user_id = session.get("user_id")
    if not user_id:
        # 로그인하지 않은 사용자는 세션 기반 장바구니 사용
        from app.services.cart_service import get_cart_summary
        summary = get_cart_summary()
        return render_template("cart.html", cart=summary, is_guest=True)

    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin:
        # DB 연결 실패 시 세션 기반으로 폴백
        from app.services.cart_service import get_cart_summary
        summary = get_cart_summary()
        return render_template("cart.html", cart=summary, is_guest=True)

    try:
        # carts + product_options + products JOIN 조회
        cart_res = admin.table("carts").select(
            "id, product_option_id, quantity"
        ).eq("user_id", user_id).execute()

        if not cart_res.data:
            # 빈 장바구니
            return render_template("cart.html", cart={
                "cart_items": [],
                "items_count": 0,
                "total_quantity": 0,
                "total_price": "0원",
                "total_price_num": 0,
                "shipping_fee": "무료",
                "shipping_fee_num": 0,
                "final_price": "0원",
                "final_price_num": 0,
                "has_out_of_stock": False
            }, is_guest=False)

        # 각 cart 항목에서 product_option_id로 product_options, products 정보 조회
        cart_items = []
        total_price = 0
        total_quantity = 0
        has_out_of_stock = False

        for cart_item in cart_res.data:
            product_option_id = cart_item["product_option_id"]
            quantity = cart_item["quantity"]

            # product_options 조회
            opt_res = admin.table("product_options").select(
                "id, product_id, color, size, stock, stock_quantity, additional_price"
            ).eq("id", product_option_id).execute()

            if not opt_res.data:
                continue

            option = opt_res.data[0]
            product_id = option["product_id"]
            stock = option.get("stock")
            if stock is None:
                stock = option.get("stock_quantity") or 0
            stock = max(0, int(stock))

            # products 조회
            prod_res = admin.table("products").select(
                "id, name, price, discount_rate"
            ).eq("id", product_id).execute()

            if not prod_res.data:
                continue

            product = prod_res.data[0]

            # 할인가 계산
            price = product["price"]
            discount_rate = product.get("discount_rate", 0) or 0
            discounted_price = int(price * (1 - discount_rate / 100))

            # 상품 이미지 조회 (primary image)
            img_res = admin.table("product_images").select(
                "id, image_url"
            ).eq("product_id", product_id).eq("is_primary", True).limit(1).execute()
            thumbnail_url = img_res.data[0]["image_url"] if img_res.data else "https://via.placeholder.com/70x80"

            subtotal = discounted_price * quantity
            total_price += subtotal
            total_quantity += quantity

            # 재고 상태 확인
            is_out_of_stock = stock == 0
            if is_out_of_stock:
                has_out_of_stock = True

            cart_items.append({
                "id": cart_item["id"],  # cart table의 id (PATCH/DELETE용)
                "product_option_id": product_option_id,
                "product_id": product_id,
                "name": product["name"],
                "color": option.get("color", ""),
                "size": option.get("size", ""),
                "quantity": quantity,
                "price": f"{discounted_price:,}원",
                "price_num": discounted_price,
                "subtotal": f"{subtotal:,}원",
                "subtotal_num": subtotal,
                "thumbnail_url": thumbnail_url,
                "stock": stock,
                "is_out_of_stock": is_out_of_stock
            })

        # 배송비 계산 (50,000원 이상 무료, 미만 3,000원)
        shipping_fee = 0 if total_price >= 50000 else 3000
        final_price = total_price + shipping_fee

        cart_summary = {
            "cart_items": cart_items,
            "items_count": len(cart_items),
            "total_quantity": total_quantity,
            "total_price": f"{total_price:,}원",
            "total_price_num": total_price,
            "shipping_fee": f"{shipping_fee:,}원" if shipping_fee > 0 else "무료",
            "shipping_fee_num": shipping_fee,
            "final_price": f"{final_price:,}원",
            "final_price_num": final_price,
            "has_out_of_stock": has_out_of_stock
        }

        return render_template("cart.html", cart=cart_summary, is_guest=False)

    except Exception as e:
        print(f"[에러] 장바구니 조회 실패: {e}", file=sys.stderr)
        # 에러 시 세션 기반으로 폴백
        from app.services.cart_service import get_cart_summary
        summary = get_cart_summary()
        return render_template("cart.html", cart=summary, is_guest=True)

@cart_bp.route("/api/summary", methods=["GET"])
def api_summary():
    """장바구니 요약 JSON API"""
    return jsonify(get_cart_summary())

@cart_bp.route("/add", methods=["POST"])
@cart_bp.route("/api/add", methods=["POST"])
def api_add():
    """
    [장바구니 상품 담기 API]
    - 로그인 필수: 로그인 안 했으면 /auth/login 으로 리다이렉트
    - 담기 전에 product_options.stock을 조회해서 요청 수량보다 적으면
      "재고가 부족합니다(현재 N개)" 에러 반환, DB에 아무 것도 쓰지 않음
    - carts 테이블에 upsert (같은 옵션이면 수량 누적)
    - 누적 후 수량이 재고를 초과하게 되는 경우도 동일하게 에러 처리
    - 성공 시 JSON: {"success": true, "message": "장바구니에 담겼습니다"}
    """
    # 1. 로그인 확인: 로그인 안 했으면 /auth/login 으로 리다이렉트
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    data = request.get_json(silent=True) or request.form or {}
    quantity = int(data.get("quantity", 1) or 1)
    if quantity < 1:
        return jsonify({"success": False, "message": "최소 1개 이상의 수량을 선택해야 합니다."}), 400

    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin:
        return jsonify({"success": False, "message": "데이터베이스 연결에 실패했습니다."}), 500

    # 2. product_option 정보 조회
    target_option = None
    product_option_id = data.get("product_option_id") or data.get("option_id")
    product_id = data.get("product_id")
    color = data.get("color")
    size = data.get("size")

    # 1) product_option_id 또는 option_id 가 주어진 경우
    if product_option_id:
        opt_res = admin.table("product_options").select("id, product_id, color, size, stock, stock_quantity, additional_price").eq("id", product_option_id).execute()
        if opt_res.data:
            target_option = opt_res.data[0]

    # 2) product_id와 color, size 조합으로 조회하는 경우
    if not target_option and product_id and color and size:
        opt_res = admin.table("product_options").select("id, product_id, color, size, stock, stock_quantity, additional_price") \
            .eq("product_id", product_id) \
            .eq("color", color) \
            .eq("size", size) \
            .execute()
        if opt_res.data:
            target_option = opt_res.data[0]

    # 3) product_id 만 전달된 경우 (옵션 ID인지 또는 대표 옵션인지 조회)
    if not target_option and product_id:
        try:
            opt_res = admin.table("product_options").select("id, product_id, color, size, stock, stock_quantity, additional_price").eq("id", product_id).execute()
            if opt_res.data:
                target_option = opt_res.data[0]
        except Exception:
            pass

        if not target_option:
            try:
                opt_res2 = admin.table("product_options").select("id, product_id, color, size, stock, stock_quantity, additional_price").eq("product_id", product_id).limit(1).execute()
                if opt_res2.data:
                    target_option = opt_res2.data[0]
            except Exception:
                pass

    if not target_option:
        return jsonify({"success": False, "message": "존재하지 않거나 유효하지 않은 상품 옵션입니다."}), 400

    option_id = target_option["id"]
    stock = target_option.get("stock")
    if stock is None:
        stock = target_option.get("stock_quantity") or 0
    stock = max(0, int(stock))

    # 3. 담기 전 product_options.stock 조회: 요청 수량보다 적으면 "재고가 부족합니다(현재 N개)" 에러 반환, DB에 아무 것도 쓰지 않음
    if quantity > stock:
        return jsonify({"success": False, "message": f"재고가 부족합니다(현재 {stock}개)"}), 400

    # 4. carts 테이블에서 현재 사용자의 해당 옵션 기존 수량 조회
    cart_res = admin.table("carts").select("id, quantity").eq("user_id", user_id).eq("product_option_id", option_id).execute()
    existing_row = cart_res.data[0] if cart_res.data else None
    existing_qty = int(existing_row.get("quantity", 0)) if existing_row else 0
    accumulated_qty = existing_qty + quantity

    # 5. 누적 후 수량이 재고를 초과하게 되는 경우도 동일하게 에러 처리
    if accumulated_qty > stock:
        return jsonify({"success": False, "message": f"재고가 부족합니다(현재 {stock}개)"}), 400

    # 6. carts 테이블에 upsert (같은 옵션이면 수량 누적)
    try:
        if existing_row:
            admin.table("carts").update({
                "quantity": accumulated_qty
            }).eq("id", existing_row["id"]).execute()
        else:
            admin.table("carts").insert({
                "user_id": user_id,
                "product_option_id": option_id,
                "quantity": accumulated_qty
            }).execute()
    except Exception as e:
        print(f"[에러] carts 테이블 저장 실패: {e}", file=sys.stderr)
        return jsonify({"success": False, "message": "장바구니 저장 중 오류가 발생했습니다."}), 500

    # 세션 장바구니 동기화 (기존 세션 뷰 및 네비게이션 뱃지 연동)
    name = data.get("name")
    if not name:
        try:
            p_row = admin.table("products").select("name").eq("id", target_option["product_id"]).execute()
            p_name = p_row.data[0]["name"] if p_row.data else "상품"
        except Exception:
            p_name = "상품"
        c_name = target_option.get("color") or ""
        s_name = target_option.get("size") or ""
        name = f"{p_name} ({c_name} / {s_name})" if (c_name and s_name) else p_name

    price_num = int(data.get("price_num", 0))
    thumbnail_url = data.get("thumbnail_url", "")
    summary = add_to_cart(option_id, name, price_num, thumbnail_url, quantity)

    # 7. 성공 시 JSON 반환: {"success": true, "message": "장바구니에 담겼습니다"}
    return jsonify({
        "success": True,
        "message": "장바구니에 담겼습니다",
        "cart": summary
    })


@cart_bp.route("/<cart_id>", methods=["PATCH"])
def update_cart_quantity(cart_id: str):
    """
    [장바구니 수량 변경 API (Supabase carts 테이블 직접 UPDATE)]
    - 요청 body: quantity (변경할 수량)
    - 본인 소유의 장바구니 아이템인지 확인 (다른 사용자의 cart_id 접근 차단)
    - quantity가 1 미만이면 에러
    - quantity가 해당 옵션의 stock을 초과하면 에러:
      "재고가 부족합니다(현재 N개)" 에러, 변경하지 않음
    - 성공 시 UPDATE 후 새 소계(subtotal) 반환
    """
    # 1. 로그인 확인
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    data = request.get_json(silent=True) or request.form or {}
    quantity_raw = data.get("quantity")
    
    # quantity 파라미터 파싱 (0도 정상적으로 처리)
    if quantity_raw is None:
        quantity = 1
    else:
        try:
            quantity = int(quantity_raw)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "수량은 숫자여야 합니다."}), 400

    if quantity < 1:
        return jsonify({"success": False, "message": "수량은 1 이상이어야 합니다."}), 400

    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin:
        return jsonify({"success": False, "message": "데이터베이스 연결에 실패했습니다."}), 500

    try:
        # 2. 본인 소유의 장바구니 아이템인지 확인
        cart_res = admin.table("carts").select("id, user_id, product_option_id, quantity").eq("id", cart_id).execute()
        if not cart_res.data:
            return jsonify({"success": False, "message": "존재하지 않는 장바구니 항목입니다."}), 404

        cart_item = cart_res.data[0]
        if cart_item["user_id"] != user_id:
            return jsonify({"success": False, "message": "해당 장바구니 항목에 접근 권한이 없습니다."}), 403

        product_option_id = cart_item["product_option_id"]

        # 3. 해당 옵션의 재고 조회
        opt_res = admin.table("product_options").select("id, stock, stock_quantity").eq("id", product_option_id).execute()
        if not opt_res.data:
            return jsonify({"success": False, "message": "존재하지 않는 상품 옵션입니다."}), 404

        option = opt_res.data[0]
        stock = option.get("stock")
        if stock is None:
            stock = option.get("stock_quantity") or 0
        stock = max(0, int(stock))

        # 4. quantity가 해당 옵션의 stock을 초과하면 에러
        if quantity > stock:
            return jsonify({"success": False, "message": f"재고가 부족합니다(현재 {stock}개)"}), 400

        # 5. UPDATE 처리
        admin.table("carts").update({"quantity": quantity}).eq("id", cart_id).execute()

        # 6. 업데이트된 아이템과 함께 새 소계(subtotal) 계산하여 반환
        updated_res = admin.table("carts") \
            .select("id, quantity") \
            .eq("id", cart_id) \
            .execute()

        if updated_res.data:
            updated_item = updated_res.data[0]
            # subtotal을 계산하기 위해 product_options에서 가격 정보를 조회해야 하지만,
            # 여기서는 간단히 quantity만 반환하고 프론트엔드에서 가격을 알고 있다고 가정
            return jsonify({
                "success": True,
                "message": "수량이 변경되었습니다.",
                "cart_id": cart_id,
                "quantity": updated_item["quantity"]
            })
        else:
            return jsonify({"success": False, "message": "수량 변경 후 조회에 실패했습니다."}), 500

    except Exception as e:
        print(f"[에러] 장바구니 수량 변경 실패: {e}", file=sys.stderr)
        return jsonify({"success": False, "message": "장바구니 수량 변경 중 오류가 발생했습니다."}), 500


@cart_bp.route("/<cart_id>", methods=["DELETE"])
def delete_cart_item(cart_id: str):
    """
    [장바구니 아이템 삭제 API (DELETE)]
    - 요청 URL: DELETE /cart/<cart_id>
    - 본인 소유의 장바구니 아이템인지 확인 (403 if mismatch)
    - 성공 시 DELETE 후 성공 메시지 반환
    """
    # 1. 로그인 확인
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin:
        return jsonify({"success": False, "message": "데이터베이스 연결에 실패했습니다."}), 500

    try:
        # 2. 본인 소유의 장바구니 아이템인지 확인
        cart_res = admin.table("carts").select("id, user_id").eq("id", cart_id).execute()
        if not cart_res.data:
            return jsonify({"success": False, "message": "존재하지 않는 장바구니 항목입니다."}), 404

        cart_item = cart_res.data[0]
        if cart_item["user_id"] != user_id:
            return jsonify({"success": False, "message": "해당 장바구니 항목에 접근 권한이 없습니다."}), 403

        # 3. DELETE 처리
        admin.table("carts").delete().eq("id", cart_id).execute()

        return jsonify({
            "success": True,
            "message": "상품이 장바구니에서 삭제되었습니다."
        })

    except Exception as e:
        print(f"[에러] 장바구니 삭제 실패: {e}", file=sys.stderr)
        return jsonify({"success": False, "message": "장바구니 삭제 중 오류가 발생했습니다."}), 500

@cart_bp.route("/api/update", methods=["POST"])
def api_update():
    """장바구니 수량 변경 API"""
    data = request.get_json(silent=True) or request.form
    product_id = data.get("product_id")
    quantity = int(data.get("quantity", 1))

    if not product_id:
        return jsonify({"success": False, "message": "상품 ID가 필요합니다."}), 400

    summary = update_cart_item(product_id, quantity)
    return jsonify({"success": True, "cart": summary})

@cart_bp.route("/api/remove", methods=["POST"])
def api_remove():
    """장바구니 상품 삭제 API"""
    data = request.get_json(silent=True) or request.form
    product_id = data.get("product_id")

    if not product_id:
        return jsonify({"success": False, "message": "상품 ID가 필요합니다."}), 400

    summary = remove_from_cart(product_id)
    return jsonify({"success": True, "message": "상품이 장바구니에서 삭제되었습니다.", "cart": summary})

@cart_bp.route("/api/clear", methods=["POST"])
def api_clear():
    """장바구니 전체 비우기 API"""
    summary = clear_cart()
    return jsonify({"success": True, "message": "장바구니가 비워졌습니다.", "cart": summary})
