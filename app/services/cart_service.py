"""
장바구니 서비스 모듈 (cart_service.py)
- 세션 기반 임시 장바구니 (비로그인 사용자용)
- Supabase DB 기반 장바구니 (로그인 사용자용, N+1 쿼리 최적화)
- 추가(add), 수량변경(update), 삭제(remove), 비우기(clear), 요약정보(get_summary) 제공
"""

import sys
from flask import session
from app.services.supabase_client import get_supabase_client, get_admin_supabase_client

CART_SESSION_KEY = "vibe_cart"
FREE_SHIPPING_THRESHOLD = 50000
DEFAULT_SHIPPING_FEE = 3000

def get_cart() -> dict:
    """세션에서 장바구니 객체를 가져옵니다. 없으면 기본 구조 반환."""
    return session.get(CART_SESSION_KEY, {})

def save_cart(cart: dict) -> None:
    """장바구니 객체를 세션에 저장합니다."""
    session[CART_SESSION_KEY] = cart
    session.modified = True

def add_to_cart(product_id: str, name: str, price_num: int, thumbnail_url: str, quantity: int = 1) -> dict:
    """
    장바구니에 상품을 추가합니다.
    이미 존재하면 수량을 증가시킵니다.
    """
    cart = get_cart()
    product_id = str(product_id)
    quantity = max(1, int(quantity))

    if product_id in cart:
        cart[product_id]["quantity"] += quantity
    else:
        cart[product_id] = {
            "id": product_id,
            "name": name,
            "price": f"{int(price_num):,}원",
            "price_num": int(price_num),
            "thumbnail_url": thumbnail_url,
            "quantity": quantity
        }

    save_cart(cart)
    return get_cart_summary()

def update_cart_item(product_id: str, quantity: int) -> dict:
    """상품 수량을 변경합니다. 0 이하일 경우 삭제 처리합니다."""
    cart = get_cart()
    product_id = str(product_id)

    if product_id in cart:
        if quantity <= 0:
            del cart[product_id]
        else:
            cart[product_id]["quantity"] = int(quantity)
        save_cart(cart)

    return get_cart_summary()

def remove_from_cart(product_id: str) -> dict:
    """장바구니에서 특정 상품을 제거합니다."""
    cart = get_cart()
    product_id = str(product_id)

    if product_id in cart:
        del cart[product_id]
        save_cart(cart)

    return get_cart_summary()

def clear_cart() -> dict:
    """장바구니를 전체 비웁니다."""
    save_cart({})
    return get_cart_summary()

def get_cart_summary() -> dict:
    """
    현재 장바구니의 전체 목록, 총 수량, 총 주문금액, 배송비 및 최종 결제금액을 계산하여 반환합니다.
    - 기본 3만원 이상 구매 시 무료배송, 미만 시 배송비 3,000원
    """
    cart = get_cart()
    items = []
    total_quantity = 0
    total_price = 0

    for item in cart.values():
        subtotal = item["price_num"] * item["quantity"]
        items.append({
            **item,
            "subtotal": f"{subtotal:,}원",
            "subtotal_num": subtotal
        })
        total_quantity += item["quantity"]
        total_price += subtotal

    shipping_fee = 0 if (total_price >= 30000 or total_price == 0) else 3000
    final_price = total_price + shipping_fee

    return {
        "cart_items": items,
        "items_count": len(items),
        "total_quantity": total_quantity,
        "total_price": f"{total_price:,}원",
        "total_price_num": total_price,
        "shipping_fee": f"{shipping_fee:,}원" if shipping_fee > 0 else "무료",
        "shipping_fee_num": shipping_fee,
        "final_price": f"{final_price:,}원",
        "final_price_num": final_price
    }


def get_user_db_cart(user_id: str) -> dict:
    """
    [Supabase DB 기반 장바구니 요약 조회 - N+1 쿼리 최적화]
    - carts + product_options + products 테이블을 중첩 단일 쿼리로 조회
    - 상품 대표 이미지를 product_id 배치 쿼리로 일괄 매핑 (총 2회 쿼리로 완료)
    - 장바구니 뷰와 주문서(Checkout) 뷰에서 모두 완벽히 호환되는 표준 데이터 구조 반환
    """
    empty_result = {
        "is_empty": True,
        "has_out_of_stock": False,
        "cart_items": [],
        "items_count": 0,
        "total_quantity": 0,
        "total_price": "0원",
        "total_price_num": 0,
        "total_price_formatted": "0원",
        "shipping_fee": "무료",
        "shipping_fee_num": 0,
        "shipping_fee_formatted": "무료",
        "final_price": "0원",
        "final_price_num": 0,
        "final_price_formatted": "0원"
    }

    if not user_id:
        return empty_result

    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin:
        return empty_result

    try:
        # 1. carts + product_options + products 중첩 단일 조회
        cart_res = admin.table("carts").select(
            "id, product_option_id, quantity, "
            "product_options(id, product_id, color, size, stock, stock_quantity, additional_price, "
            "products(id, name, price, discount_rate))"
        ).eq("user_id", user_id).execute()

        raw_rows = cart_res.data or []
        if not raw_rows:
            return empty_result

        # 2. 고유 product_id 목록 추출 후 대표 이미지 배치 쿼리 (1회)
        product_ids = []
        for row in raw_rows:
            opt = row.get("product_options") or {}
            pid = opt.get("product_id")
            if pid and pid not in product_ids:
                product_ids.append(pid)

        image_map = {}
        if product_ids:
            img_res = admin.table("product_images").select("product_id, image_url")\
                .eq("is_primary", True)\
                .in_("product_id", product_ids)\
                .execute()
            for img in (img_res.data or []):
                image_map[img["product_id"]] = img["image_url"]

        # 3. 항목별 단가, 소계 및 재고 검증
        cart_items = []
        total_price = 0
        total_quantity = 0
        has_out_of_stock = False

        for row in raw_rows:
            cart_id = row["id"]
            option_id = row["product_option_id"]
            quantity = max(1, int(row.get("quantity") or 1))

            opt = row.get("product_options") or {}
            if not opt:
                continue

            product = opt.get("products") or {}
            if not product:
                continue

            product_id = opt.get("product_id")
            original_price = int(product.get("price") or 0)
            discount_rate = float(product.get("discount_rate") or 0)
            discounted_price = int(original_price * (1 - discount_rate / 100))

            subtotal = discounted_price * quantity
            total_price += subtotal
            total_quantity += quantity

            stock = opt.get("stock")
            if stock is None:
                stock = opt.get("stock_quantity") or 0
            stock = max(0, int(stock))

            is_out_of_stock = (stock == 0)
            if is_out_of_stock:
                has_out_of_stock = True

            thumbnail_url = image_map.get(product_id) or "https://via.placeholder.com/70x80"

            cart_items.append({
                "id": cart_id,
                "cart_id": cart_id,
                "product_id": product_id,
                "product_option_id": option_id,
                "name": product.get("name") or "상품명 없음",
                "color": opt.get("color") or "-",
                "size": opt.get("size") or "-",
                "quantity": quantity,
                "price": f"{discounted_price:,}원",
                "price_num": discounted_price,
                "price_formatted": f"{discounted_price:,}원",
                "subtotal": f"{subtotal:,}원",
                "subtotal_num": subtotal,
                "subtotal_formatted": f"{subtotal:,}원",
                "thumbnail_url": thumbnail_url,
                "stock": stock,
                "is_out_of_stock": is_out_of_stock
            })

        if not cart_items:
            return empty_result

        # 배송비 계산: 50,000원 이상 무료, 미만 3,000원
        shipping_fee = 0 if total_price >= FREE_SHIPPING_THRESHOLD else DEFAULT_SHIPPING_FEE
        final_price = total_price + shipping_fee

        return {
            "is_empty": False,
            "has_out_of_stock": has_out_of_stock,
            "cart_items": cart_items,
            "items_count": len(cart_items),
            "total_quantity": total_quantity,
            "total_price": f"{total_price:,}원",
            "total_price_num": total_price,
            "total_price_formatted": f"{total_price:,}원",
            "shipping_fee": f"{shipping_fee:,}원" if shipping_fee > 0 else "무료",
            "shipping_fee_num": shipping_fee,
            "shipping_fee_formatted": f"{shipping_fee:,}원" if shipping_fee > 0 else "무료",
            "final_price": f"{final_price:,}원",
            "final_price_num": final_price,
            "final_price_formatted": f"{final_price:,}원"
        }
    except Exception as e:
        print(f"[에러] DB 장바구니 조회 실패: {e}", file=sys.stderr)
        return empty_result
