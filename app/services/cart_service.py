"""
장바구니 서비스 모듈
- Flask session 기반으로 비로그인/로그인 사용자 모두 빠르고 안정적으로 동작
- 장바구니 항목: product_id, name, price, price_num, thumbnail_url, quantity, subtotal
- 추가(add), 수량변경(update), 삭제(remove), 비우기(clear), 요약정보(get_summary) 제공
"""

from flask import session

CART_SESSION_KEY = "vibe_cart"

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
