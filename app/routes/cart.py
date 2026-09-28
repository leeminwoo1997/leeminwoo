"""
장바구니(Cart) 라우트 블루프린트
- GET /cart : 장바구니 페이지 렌더링
- GET /cart/api/summary : 현재 장바구니 요약 정보 JSON 반환 (비동기 연동용)
- POST /cart/api/add : 장바구니 상품 추가 API
- POST /cart/api/update : 장바구니 수량 변경 API
- POST /cart/api/remove : 장바구니 상품 삭제 API
- POST /cart/api/clear : 장바구니 비우기 API
"""

from flask import Blueprint, render_template, request, jsonify
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
    """장바구니 전체 페이지 렌더링"""
    summary = get_cart_summary()
    return render_template("cart.html", cart=summary)

@cart_bp.route("/api/summary", methods=["GET"])
def api_summary():
    """장바구니 요약 JSON API"""
    return jsonify(get_cart_summary())

@cart_bp.route("/api/add", methods=["POST"])
def api_add():
    """장바구니 상품 담기 API"""
    data = request.get_json(silent=True) or request.form
    product_id = data.get("product_id")
    name = data.get("name", "상품")
    price_num = int(data.get("price_num", 0))
    thumbnail_url = data.get("thumbnail_url", "")
    quantity = int(data.get("quantity", 1))

    if not product_id or price_num < 0:
        return jsonify({"success": False, "message": "잘못된 상품 정보입니다."}), 400

    summary = add_to_cart(product_id, name, price_num, thumbnail_url, quantity)
    return jsonify({"success": True, "message": f"'{name}' 상품이 장바구니에 담겼습니다.", "cart": summary})

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
