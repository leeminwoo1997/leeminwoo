"""
주문(Order) 라우트 블루프린트
- GET /order/checkout : 주문서 작성 페이지
- POST /order/checkout : 주문 및 결제(더미 결제) 처리
- GET /order/complete/<order_number> : 주문 완료 페이지
- GET /order/api/default-shipping : 기본 배송지 정보 비동기 조회 API
"""

import sys
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from app.services.auth_service import login_required
from app.services.order_service import (
    get_checkout_data,
    create_order,
    get_order_by_number,
    get_default_shipping_info
)

order_bp = Blueprint("order", __name__, url_prefix="/order")


@order_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    """
    [주문서 페이지 및 결제 처리]
    - GET /order/checkout
      1. 로그인 필수 (미로그인 시 /auth/login 리다이렉트)
      2. 장바구니 비어있으면 /cart 리다이렉트
      3. 품절(stock=0) 아이템이 하나라도 있으면 /cart 리다이렉트 후
         "품절된 상품이 있어 주문할 수 없습니다" 안내
      4. 장바구니 아이템 목록 표시 (수정 불가)
      5. 배송지 입력 폼 (수령인 이름, 010-0000-0000 패턴 휴대폰 번호, 5자 이상 배송 주소, 메모)
      6. 기본 배송지 불러오기 버튼 (profiles 테이블 조회)
      7. 결제 금액 요약 (상품금액 + 배송비 = 최종금액)
      8. 더미 결제하기 버튼 (중복 클릭 방지)
    
    - POST /order/checkout
      1. 폼 데이터 유효성 검증
      2. 주문 생성 및 더미 결제 완료 처리
      3. 장바구니 비우기 및 재고 차감
      4. 주문 완료 페이지로 리다이렉트
    """
    user_id = session.get("user_id")

    # 1. 장바구니 및 주문 준비 데이터 조회
    checkout_data = get_checkout_data(user_id)

    # 2. 장바구니가 비어있는 경우 /cart 리다이렉트
    if checkout_data["is_empty"]:
        flash("장바구니가 비어 있어 주문서 작성을 진행할 수 없습니다.", "warning")
        return redirect(url_for("cart.view_cart"))

    # 3. 장바구니에 품절(stock=0) 아이템이 하나라도 있는 경우 /cart 리다이렉트
    if checkout_data["has_out_of_stock"]:
        flash("품절된 상품이 있어 주문할 수 없습니다.", "danger")
        return redirect(url_for("cart.view_cart", error="out_of_stock"))

    # POST: 결제하기 제출 처리
    if request.method == "POST":
        form_data = {
            "recipient_name": request.form.get("recipient_name", ""),
            "recipient_phone": request.form.get("recipient_phone", ""),
            "shipping_address": request.form.get("shipping_address", ""),
            "shipping_memo": request.form.get("shipping_memo", "")
        }

        success, message, order_number = create_order(user_id, form_data)

        if not success:
            # 실패 시 에러 메시지와 함께 주문서 폼 재표시
            return render_template(
                "order/checkout.html",
                checkout=checkout_data,
                form=form_data,
                error=message
            )

        # 성공 시 주문 완료 페이지로 이동
        return redirect(url_for("order.order_complete", order_number=order_number))

    # GET: 주문서 페이지 렌더링
    return render_template(
        "order/checkout.html",
        checkout=checkout_data,
        form=checkout_data.get("default_shipping", {}),
        error=None
    )


@order_bp.route("/complete/<order_number>")
@login_required
def order_complete(order_number: str):
    """
    [주문 완료 페이지]
    - 주문 완료 확인 및 주문 상세 요약 안내
    - 본인의 주문인지 확인 후 렌더링
    """
    user_id = session.get("user_id")
    order = get_order_by_number(order_number, user_id=user_id)

    if not order:
        flash("해당 주문 정보를 찾을 수 없습니다.", "danger")
        return redirect(url_for("main.index"))

    return render_template(
        "order/complete.html",
        order=order,
        order_items=order.get("order_items", [])
    )


@order_bp.route("/api/default-shipping", methods=["GET"])
@login_required
def api_default_shipping():
    """
    로그인 사용자의 기본 배송지 정보 비동기(AJAX) 조회 API
    (profiles 테이블 조회)
    """
    user_id = session.get("user_id")
    shipping_info = get_default_shipping_info(user_id)
    return jsonify({
        "success": True,
        "shipping": shipping_info
    })
