"""
주문(Order) 라우트 블루프린트
- GET /order/checkout : 주문서 작성 페이지
- POST /order/create : 주문 생성 및 결제(더미 결제) 처리 (8단계 처리 순서 준수)
- POST /order/checkout : 주문 생성 처리 (POST /order/create와 동일 동작 지원)
- GET /order/complete/<order_id> : 주문 완료 페이지
- GET /order/api/default-shipping : 기본 배송지 정보 비동기 조회 API
"""

import sys
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from app.services.auth_service import login_required
from app.services.order_service import (
    get_checkout_data,
    create_order,
    get_order_by_identifier,
    get_default_shipping_info
)

order_bp = Blueprint("order", __name__, url_prefix="/order")


@order_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    """
    [주문서 페이지]
    - GET:
      1. 로그인 필수 (미로그인 시 /auth/login 리다이렉트)
      2. 장바구니 비어있으면 /cart 리다이렉트
      3. 품절(stock=0) 아이템이 하나라도 있으면 /cart 리다이렉트 후
         "품절된 상품이 있어 주문할 수 없습니다" 안내
      4. 장바구니 아이템 목록 표시 (수정 불가)
      5. 배송지 입력 폼 (수령인 이름, 010-0000-0000 패턴 휴대폰 번호, 5자 이상 배송 주소, 메모)
      6. 기본 배송지 불러오기 버튼 (profiles 테이블 조회)
      7. 결제 금액 요약 (상품금액 + 배송비 = 최종금액)
      8. 더미 결제하기 버튼 (중복 클릭 방지)
    
    - POST:
      주문 생성 처리 (/order/create 로 전달)
    """
    if request.method == "POST":
        return create_order_route()

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

    # GET: 주문서 페이지 렌더링
    return render_template(
        "order/checkout.html",
        checkout=checkout_data,
        form=checkout_data.get("default_shipping", {}),
        error=None
    )


@order_bp.route("/create", methods=["POST"])
@login_required
def create_order_route():
    """
    [주문 생성 처리: POST /order/create]
    처리 순서 (반드시 이 순서로):
    1. 장바구니 조회 + 재고 확인 (재고 부족 시 에러, 처리 중단, 아무 것도 쓰지 않음)
    2. 배송지 입력값 서버 측 재검증 (휴대폰 번호 패턴, 주소 최소 길이)
    3. 주문번호 생성: 'VF-' + 오늘날짜(YYYYMMDD) + '-' + 4자리 랜덤숫자 + 밀리초 타임스탬프 뒷 3자리
    4. orders 테이블에 INSERT (status='paid', paid_at=now())
    5. order_items INSERT (상품명, 색상, 사이즈, 가격 스냅샷)
    6. product_options.stock 차감 — 반드시 조건부 UPDATE 사용:
       UPDATE ... SET stock = stock - 수량 WHERE id = 옵션ID AND stock >= 수량
       영향받은 행이 0개면 "방금 재고가 소진되었습니다" 에러로 롤백 처리
    7. carts 아이템 DELETE
    8. /order/complete/<order_id> 리다이렉트
    기술: service_role 키로 재고 차감 (RLS 우회 필요)
    """
    user_id = session.get("user_id")

    form_data = {
        "recipient_name": request.form.get("recipient_name", ""),
        "recipient_phone": request.form.get("recipient_phone", ""),
        "shipping_address": request.form.get("shipping_address", ""),
        "shipping_memo": request.form.get("shipping_memo", "")
    }

    success, message, order_id = create_order(user_id, form_data)

    if not success:
        # 실패 시 에러 메시지와 함께 주문서 폼 재표시 또는 장바구니 리다이렉트
        checkout_data = get_checkout_data(user_id)
        if checkout_data["is_empty"] or checkout_data["has_out_of_stock"]:
            flash(message, "danger")
            return redirect(url_for("cart.view_cart", error=message))

        return render_template(
            "order/checkout.html",
            checkout=checkout_data,
            form=form_data,
            error=message
        )

    # 8. /order/complete/<order_id> 리다이렉트
    return redirect(url_for("order.order_complete", order_id=order_id))


@order_bp.route("/complete/<order_id>")
@login_required
def order_complete(order_id: str):
    """
    [주문 완료 페이지: GET /order/complete/<order_id>]
    - 본인 주문이 맞는지 확인 (다른 사용자의 order_id 접근 차단: 403 Forbidden)
    - 주문번호, 배송지, 주문 상품 목록, 결제 금액 표시
    - "마이페이지로", "쇼핑 계속하기" 버튼 제공
    """
    user_id = session.get("user_id")

    # 1. order_id (또는 order_number)로 주문 조회 (사용자 제한 없이 조회 후 소유권 체크)
    admin = get_default_shipping_info(user_id)  # noqa
    order = get_order_by_identifier(order_id)

    if not order:
        flash("해당 주문 정보를 찾을 수 없습니다.", "danger")
        return redirect(url_for("main.index"))

    # 2. 본인 주문이 맞는지 확인 (다른 사용자의 order_id 접근 차단)
    if str(order.get("user_id")) != str(user_id):
        from flask import abort
        abort(403)

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
    shipping_info = get_default_shipping_info(user_id)
    return jsonify({
        "success": True,
        "shipping": shipping_info
    })
