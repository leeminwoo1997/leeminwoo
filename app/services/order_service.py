"""
주문(Order) 서비스 모듈
- 주문서 결제 준비 데이터 조회 (장바구니 확인, 품절 체크, 결제 금액 계산)
- 프로필 테이블(profiles) 기반 기본 배송지 정보 조회
- 주문 및 결제(더미 결제) 처리 로직 (주문 번호 생성, 재고 차감, 장바구니 비우기)
- 주문 완료 내역 조회
"""

import sys
import re
import uuid
from datetime import datetime, timezone
from app.services.supabase_client import get_supabase_client, get_admin_supabase_client


def get_default_shipping_info(user_id: str) -> dict:
    """
    로그인한 사용자의 기본 배송지 정보 조회 (profiles 테이블 기반)
    - profiles 테이블에서 이름(full_name), 연락처(phone_number) 조회
    - profiles 테이블에 address 컬럼이 있으면 주소 조회, 없거나 비어있으면 최근 orders 테이블에서 조회
    """
    client = get_admin_supabase_client() or get_supabase_client()
    default_info = {
        "recipient_name": "",
        "recipient_phone": "",
        "shipping_address": "",
        "shipping_memo": ""
    }

    if not client or not user_id:
        return default_info

    try:
        # 1. profiles 테이블 조회
        profile_res = client.table("profiles").select("*").eq("id", user_id).execute()
        if profile_res.data and len(profile_res.data) > 0:
            profile = profile_res.data[0]
            default_info["recipient_name"] = profile.get("full_name") or ""
            default_info["recipient_phone"] = profile.get("phone_number") or ""
            # profiles 테이블에 address 컬럼이 있는 경우 사용
            if profile.get("address"):
                default_info["shipping_address"] = profile.get("address")

        # 2. 프로필에 주소가 없는 경우 최근 주문(orders)에서 배송 주소 조회
        if not default_info["shipping_address"]:
            order_res = client.table("orders").select("shipping_address, recipient_name, recipient_phone")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            if order_res.data and len(order_res.data) > 0:
                last_order = order_res.data[0]
                if not default_info["shipping_address"]:
                    default_info["shipping_address"] = last_order.get("shipping_address") or ""
                if not default_info["recipient_name"] and last_order.get("recipient_name"):
                    default_info["recipient_name"] = last_order.get("recipient_name")
                if not default_info["recipient_phone"] and last_order.get("recipient_phone"):
                    default_info["recipient_phone"] = last_order.get("recipient_phone")

    except Exception as e:
        print(f"[경고] 기본 배송지 조회 중 오류 발생: {e}", file=sys.stderr)

    return default_info


def get_checkout_data(user_id: str) -> dict:
    """
    주문서 작성 페이지에 필요한 데이터 조회 및 유효성 검증
    - 장바구니 항목 존재 여부 확인
    - 품절(stock=0) 아이템 존재 여부 확인
    - 상품금액, 배송비, 최종 결제금액 계산
    - 기본 배송지 정보 로드
    """
    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin or not user_id:
        return {
            "is_empty": True,
            "has_out_of_stock": False,
            "cart_items": [],
            "total_price": 0,
            "shipping_fee": 0,
            "final_price": 0,
            "default_shipping": get_default_shipping_info(user_id)
        }

    # 1. carts 테이블에서 사용자의 장바구니 품목 조회
    cart_res = admin.table("carts").select(
        "id, product_option_id, quantity"
    ).eq("user_id", user_id).execute()

    if not cart_res.data or len(cart_res.data) == 0:
        return {
            "is_empty": True,
            "has_out_of_stock": False,
            "cart_items": [],
            "total_price": 0,
            "shipping_fee": 0,
            "final_price": 0,
            "default_shipping": get_default_shipping_info(user_id)
        }

    cart_items = []
    total_price = 0
    total_quantity = 0
    has_out_of_stock = False

    for cart_item in cart_res.data:
        product_option_id = cart_item["product_option_id"]
        quantity = int(cart_item.get("quantity", 1) or 1)

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

        # 단가 및 할인가 계산
        original_price = int(product.get("price", 0))
        discount_rate = float(product.get("discount_rate", 0) or 0)
        discounted_price = int(original_price * (1 - discount_rate / 100))

        # 상품 이미지 조회 (대표 이미지)
        img_res = admin.table("product_images").select(
            "image_url"
        ).eq("product_id", product_id).eq("is_primary", True).limit(1).execute()
        thumbnail_url = img_res.data[0]["image_url"] if img_res.data else "https://via.placeholder.com/70x80"

        subtotal = discounted_price * quantity
        total_price += subtotal
        total_quantity += quantity

        is_out_of_stock = (stock == 0)
        if is_out_of_stock:
            has_out_of_stock = True

        cart_items.append({
            "cart_id": cart_item["id"],
            "product_id": product_id,
            "product_option_id": product_option_id,
            "name": product["name"],
            "color": option.get("color", "") or "-",
            "size": option.get("size", "") or "-",
            "quantity": quantity,
            "price": discounted_price,
            "price_formatted": f"{discounted_price:,}원",
            "subtotal": subtotal,
            "subtotal_formatted": f"{subtotal:,}원",
            "thumbnail_url": thumbnail_url,
            "stock": stock,
            "is_out_of_stock": is_out_of_stock
        })

    # 배송비 계산 정책: 50,000원 이상 무료, 미만 3,000원
    shipping_fee = 0 if total_price >= 50000 else 3000
    final_price = total_price + shipping_fee

    default_shipping = get_default_shipping_info(user_id)

    return {
        "is_empty": len(cart_items) == 0,
        "has_out_of_stock": has_out_of_stock,
        "cart_items": cart_items,
        "items_count": len(cart_items),
        "total_quantity": total_quantity,
        "total_price": total_price,
        "total_price_formatted": f"{total_price:,}원",
        "shipping_fee": shipping_fee,
        "shipping_fee_formatted": f"{shipping_fee:,}원" if shipping_fee > 0 else "무료",
        "final_price": final_price,
        "final_price_formatted": f"{final_price:,}원",
        "default_shipping": default_shipping
    }


def create_order(user_id: str, form_data: dict) -> tuple[bool, str, str]:
    """
    주문 생성 및 더미 결제 처리
    - 필수 입력값 및 형식 유효성 검증 (수령인 이름, 010-0000-0000 휴대폰 번호, 5자 이상 배송 주소)
    - 장바구니 항목 재검증 (빈 장바구니 방지, 품절 상품 방지, 재고 수량 초과 방지)
    - 고유 주문번호 생성 (ORD-YYYYMMDD-UUID)
    - orders 테이블 레코드 삽입 (status='PAID', 더미 결제 완료 처리)
    - order_items 테이블 상세 품목 일괄 삽입
    - product_options 재고 차감 처리
    - carts 테이블에서 해당 사용자의 장바구니 비우기
    반환값: (성공 여부 bool, 메시지 str, 주문번호 str)
    """
    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin:
        return False, "데이터베이스 연결에 실패했습니다.", ""

    # 1. 폼 데이터 추출 및 정제
    recipient_name = form_data.get("recipient_name", "").strip()
    recipient_phone = form_data.get("recipient_phone", "").strip()
    shipping_address = form_data.get("shipping_address", "").strip()
    shipping_memo = form_data.get("shipping_memo", "").strip()

    # 2. 유효성 검증
    if not recipient_name:
        return False, "수령인 이름을 입력해주세요.", ""

    # 휴대폰 번호 형식 검증: 010-0000-0000 패턴
    phone_pattern = r"^010-\d{4}-\d{4}$"
    if not re.match(phone_pattern, recipient_phone):
        return False, "휴대폰 번호는 010-0000-0000 형식으로 입력해주세요.", ""

    # 배송 주소 형식 검증: 최소 5자 이상
    if len(shipping_address) < 5:
        return False, "배송 주소는 5자 이상 입력해주세요.", ""

    # 3. 장바구니 상품 재확인 및 재고 유효성 검사
    checkout_data = get_checkout_data(user_id)

    if checkout_data["is_empty"]:
        return False, "장바구니가 비어 있어 주문할 수 없습니다.", ""

    if checkout_data["has_out_of_stock"]:
        return False, "품절된 상품이 있어 주문할 수 없습니다.", ""

    cart_items = checkout_data["cart_items"]
    # 수량 대비 재고 재확인
    for item in cart_items:
        if item["quantity"] > item["stock"]:
            return False, f"'{item['name']}' 상품의 재고가 부족합니다 (남은 수량: {item['stock']}개).", ""

    # 4. 고유 주문번호 생성 (예: ORD-20261002-A1B2C3)
    now_utc = datetime.now(timezone.utc)
    order_number = f"ORD-{now_utc.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

    total_amount = checkout_data["total_price"]
    shipping_fee = checkout_data["shipping_fee"]
    final_amount = checkout_data["final_price"]

    try:
        # 5. orders 테이블에 주문 생성 (더미 결제 완료이므로 status='PAID', paid_at 기록)
        order_insert_data = {
            "user_id": user_id,
            "order_number": order_number,
            "status": "PAID",
            "total_amount": total_amount,
            "discount_amount": 0,
            "final_amount": final_amount,
            "recipient_name": recipient_name,
            "recipient_phone": recipient_phone,
            "shipping_address": shipping_address,
            "shipping_memo": shipping_memo if shipping_memo else None,
            "paid_at": now_utc.isoformat(),
        }

        order_res = admin.table("orders").insert(order_insert_data).execute()
        if not order_res.data:
            return False, "주문 정보 생성에 실패했습니다.", ""

        order_id = order_res.data[0]["id"]

        # 6. order_items 테이블에 상세 품목 삽입
        order_items_to_insert = []
        for item in cart_items:
            option_desc = f"색상: {item['color']} / 사이즈: {item['size']}"
            order_items_to_insert.append({
                "order_id": order_id,
                "product_id": item["product_id"],
                "product_option_id": item["product_option_id"],
                "product_name": item["name"],
                "option_name": option_desc,
                "quantity": item["quantity"],
                "unit_price": item["price"],
                "subtotal": item["subtotal"]
            })

        admin.table("order_items").insert(order_items_to_insert).execute()

        # 7. product_options 재고 차감 처리
        for item in cart_items:
            new_stock = max(0, item["stock"] - item["quantity"])
            try:
                admin.table("product_options").update({
                    "stock": new_stock,
                    "stock_quantity": new_stock
                }).eq("id", item["product_option_id"]).execute()
            except Exception as opt_err:
                # stock 또는 stock_quantity 컬럼명 대응
                print(f"[경고] 재고 업데이트 보완 처리: {opt_err}", file=sys.stderr)
                try:
                    admin.table("product_options").update({"stock": new_stock}).eq("id", item["product_option_id"]).execute()
                except Exception:
                    admin.table("product_options").update({"stock_quantity": new_stock}).eq("id", item["product_option_id"]).execute()

        # 8. carts 테이블에서 장바구니 항목 비우기
        admin.table("carts").delete().eq("user_id", user_id).execute()

        # 사용자 프로필의 최근 배송지 정보가 없을 경우 주소 동기화 시도 (선택적)
        try:
            admin.table("profiles").update({"address": shipping_address}).eq("id", user_id).execute()
        except Exception:
            pass

        return True, "주문 및 결제가 성공적으로 완료되었습니다.", order_number

    except Exception as e:
        print(f"[에러] 주문 처리 중 예외 발생: {e}", file=sys.stderr)
        return False, f"주문 처리 중 오류가 발생했습니다: {str(e)}", ""


def get_order_by_number(order_number: str, user_id: str = None) -> dict:
    """
    주문 번호로 주문 상세 내역 및 주문 품목 조회
    """
    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin:
        return {}

    try:
        query = admin.table("orders").select("*").eq("order_number", order_number)
        if user_id:
            query = query.eq("user_id", user_id)
        order_res = query.execute()

        if not order_res.data:
            return {}

        order = order_res.data[0]

        # order_items 조회
        items_res = admin.table("order_items").select(
            "id, product_id, product_option_id, product_name, option_name, quantity, unit_price, subtotal"
        ).eq("order_id", order["id"]).execute()

        items = items_res.data or []

        # 각 아이템의 대표 이미지 조회 보완
        for item in items:
            product_id = item.get("product_id")
            if product_id:
                img_res = admin.table("product_images").select("image_url")\
                    .eq("product_id", product_id).eq("is_primary", True).limit(1).execute()
                item["thumbnail_url"] = img_res.data[0]["image_url"] if img_res.data else "https://via.placeholder.com/70x80"
            else:
                item["thumbnail_url"] = "https://via.placeholder.com/70x80"

        order["order_items"] = items
        order["order_items_list"] = items
        return order

    except Exception as e:
        print(f"[에러] 주문 번호({order_number}) 조회 실패: {e}", file=sys.stderr)
        return {}
