"""
주문(Order) 서비스 모듈
- 주문서 결제 준비 데이터 조회 (장바구니 확인, 품절 체크, 결제 금액 계산)
- 프로필 테이블(profiles) 기반 기본 배송지 정보 조회
- 주문 및 결제(더미 결제) 처리 로직:
  1. 장바구니 조회 + 재고 확인 (재고 부족 시 에러, 처리 중단, 아무 것도 쓰지 않음)
  2. 배송지 입력값 서버 측 재검증 (휴대폰 번호 패턴, 주소 최소 길이)
  3. 주문번호 생성: 'VF-' + 오늘날짜(YYYYMMDD) + '-' + 4자리 랜덤숫자 + 밀리초 타임스탬프 뒷 3자리
  4. orders 테이블에 INSERT (status='paid'/'PAID', paid_at=now())
  5. order_items INSERT (상품명, 색상, 사이즈, 가격 스냅샷)
  6. product_options.stock 차감 (조건부 UPDATE: WHERE id = 옵션ID AND stock >= 수량, 영향 행 0개면 롤백)
  7. carts 아이템 DELETE
  8. order_id 반환 -> /order/complete/<order_id> 리다이렉트 연계
- 주문 완료 내역 조회
"""

import sys
import re
import random
import time
import uuid
from datetime import datetime, timezone
from app.services.supabase_client import get_supabase_client, get_admin_supabase_client


def is_valid_uuid(val: str) -> bool:
    """주어진 문자열이 유효한 UUID 형식인지 검사"""
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


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


def create_order(user_id: str, form_data: dict) -> tuple[bool, str, str | None]:
    """
    주문 생성 및 더미 결제 처리 (POST /order/create)
    
    처리 순서 (반드시 이 순서로):
    1. 장바구니 조회 + 재고 확인 (재고 부족 시 에러, 처리 중단, 아무 것도 쓰지 않음)
    2. 배송지 입력값 서버 측 재검증 (휴대폰 번호 패턴, 주소 최소 길이)
    3. 주문번호 생성: 'VF-' + 오늘날짜(YYYYMMDD) + '-' + 4자리 랜덤숫자
       + 밀리초 타임스탬프 뒷 3자리를 덧붙여 충돌 가능성을 낮춤
    4. orders 테이블에 INSERT (status='paid'/'PAID', paid_at=now())
    5. order_items INSERT (상품명, 색상, 사이즈, 가격 스냅샷)
    6. product_options.stock 차감 — 반드시 조건부 UPDATE 사용:
       UPDATE ... SET stock = stock - 수량 WHERE id = 옵션ID AND stock >= 수량
       영향받은 행이 0개면 "방금 재고가 소진되었습니다" 에러로 롤백 처리
    7. carts 아이템 DELETE
    8. /order/complete/<order_id> 리다이렉트 지원 (order_id 반환)
    기술: service_role 키로 재고 차감 (RLS 우회 필요)

    반환값: (성공 여부 bool, 메시지 str, order_id str | None)
    """
    # 기술: service_role 키로 재고 차감 및 주문 생성 (RLS 우회)
    admin = get_admin_supabase_client()
    if not admin:
        return False, "데이터베이스 연결에 실패했습니다.", None

    # --------------------------------------------------------------------------
    # 1. 장바구니 조회 + 재고 확인 (재고 부족 시 에러, 처리 중단, 아무 것도 쓰지 않음)
    # --------------------------------------------------------------------------
    cart_res = admin.table("carts").select(
        "id, product_option_id, quantity"
    ).eq("user_id", user_id).execute()

    if not cart_res.data or len(cart_res.data) == 0:
        return False, "장바구니가 비어 있어 주문할 수 없습니다.", None

    cart_items = []
    total_amount = 0
    total_quantity = 0

    for cart_item in cart_res.data:
        product_option_id = cart_item["product_option_id"]
        quantity = int(cart_item.get("quantity", 1) or 1)

        # 실시간 재고 확인 (service_role 키 사용)
        opt_res = admin.table("product_options").select(
            "id, product_id, color, size, stock, stock_quantity, additional_price"
        ).eq("id", product_option_id).execute()

        if not opt_res.data:
            return False, "주문 상품의 옵션 정보를 찾을 수 없습니다.", None

        option = opt_res.data[0]
        stock = option.get("stock")
        if stock is None:
            stock = option.get("stock_quantity") or 0
        stock = max(0, int(stock))

        # 재고 부족 시 에러, 즉시 처리 중단 (DB에 아무 것도 쓰지 않음)
        if stock <= 0 or quantity > stock:
            return False, "품절되었거나 재고가 부족한 상품이 있어 주문할 수 없습니다.", None

        # 상품 정보 조회
        prod_res = admin.table("products").select(
            "id, name, price, discount_rate"
        ).eq("id", option["product_id"]).execute()

        if not prod_res.data:
            return False, "상품 정보를 찾을 수 없습니다.", None

        product = prod_res.data[0]
        original_price = int(product.get("price", 0))
        discount_rate = float(product.get("discount_rate", 0) or 0)
        discounted_price = int(original_price * (1 - discount_rate / 100))

        subtotal = discounted_price * quantity
        total_amount += subtotal
        total_quantity += quantity

        cart_items.append({
            "cart_id": cart_item["id"],
            "product_id": option["product_id"],
            "product_option_id": product_option_id,
            "product_name": product["name"],
            "color": option.get("color", "") or "-",
            "size": option.get("size", "") or "-",
            "quantity": quantity,
            "unit_price": discounted_price,
            "subtotal": subtotal,
            "stock": stock
        })

    # 배송비 계산 (50,000원 이상 무료, 미만 3,000원)
    shipping_fee = 0 if total_amount >= 50000 else 3000
    final_amount = total_amount + shipping_fee

    # --------------------------------------------------------------------------
    # 2. 배송지 입력값 서버 측 재검증 (휴대폰 번호 패턴, 주소 최소 길이)
    # --------------------------------------------------------------------------
    recipient_name = form_data.get("recipient_name", "").strip()
    recipient_phone = form_data.get("recipient_phone", "").strip()
    shipping_address = form_data.get("shipping_address", "").strip()
    shipping_memo = form_data.get("shipping_memo", "").strip()

    if not recipient_name:
        return False, "수령인 이름을 입력해주세요.", None

    phone_pattern = r"^010-\d{4}-\d{4}$"
    if not re.match(phone_pattern, recipient_phone):
        return False, "휴대폰 번호는 010-0000-0000 형식이어야 합니다.", None

    if len(shipping_address) < 5:
        return False, "배송 주소는 최소 5자 이상이어야 합니다.", None

    # --------------------------------------------------------------------------
    # 3. 주문번호 생성: 'VF-' + 오늘날짜(YYYYMMDD) + '-' + 4자리 랜덤숫자
    #    + 밀리초 타임스탬프 뒷 3자리를 덧붙여 충돌 가능성을 낮춤
    # --------------------------------------------------------------------------
    today_str = datetime.now().strftime("%Y%m%d")
    random_4 = f"{random.randint(1000, 9999)}"
    ms_3 = f"{int(time.time() * 1000) % 1000:03d}"
    order_number = f"VF-{today_str}-{random_4}{ms_3}"

    order_id = None
    now_utc = datetime.now(timezone.utc)

    try:
        # ----------------------------------------------------------------------
        # 4. orders 테이블에 INSERT (status='paid'/'PAID', paid_at=now())
        # ----------------------------------------------------------------------
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
            return False, "주문 정보 생성에 실패했습니다.", None

        order_id = order_res.data[0]["id"]

        # ----------------------------------------------------------------------
        # 5. order_items INSERT (상품명, 색상, 사이즈, 가격 스냅샷)
        # ----------------------------------------------------------------------
        order_items_to_insert = []
        for item in cart_items:
            option_desc = f"색상: {item['color']} / 사이즈: {item['size']}"
            order_items_to_insert.append({
                "order_id": order_id,
                "product_id": item["product_id"],
                "product_option_id": item["product_option_id"],
                "product_name": item["product_name"],
                "option_name": option_desc,
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "subtotal": item["subtotal"]
            })

        admin.table("order_items").insert(order_items_to_insert).execute()

        # ----------------------------------------------------------------------
        # 6. product_options.stock 차감 — 반드시 조건부 UPDATE 사용:
        #    UPDATE ... SET stock = stock - 수량 WHERE id = 옵션ID AND stock >= 수량
        #    영향받은 행이 0개면 "방금 재고가 소진되었습니다" 에러로 롤백 처리
        # ----------------------------------------------------------------------
        decremented_records = []
        stock_exhausted = False

        for item in cart_items:
            opt_id = item["product_option_id"]
            qty = item["quantity"]

            # 현재 실시간 재고 확인
            cur_opt_res = admin.table("product_options").select("stock, stock_quantity").eq("id", opt_id).execute()
            if not cur_opt_res.data:
                stock_exhausted = True
                break

            cur_stock = cur_opt_res.data[0].get("stock")
            if cur_stock is None:
                cur_stock = cur_opt_res.data[0].get("stock_quantity", 0)
            cur_stock = int(cur_stock or 0)

            # 이미 다른 주문에 의해 재고가 소진된 경우
            if cur_stock < qty:
                stock_exhausted = True
                break

            new_stock = max(0, cur_stock - qty)

            # 조건부 UPDATE: WHERE id = opt_id AND stock >= qty
            update_res = admin.table("product_options")\
                .update({"stock": new_stock, "stock_quantity": new_stock})\
                .eq("id", opt_id)\
                .gte("stock", qty)\
                .execute()

            # 영향받은 행이 0개인지 확인
            if not update_res.data or len(update_res.data) == 0:
                stock_exhausted = True
                break

            decremented_records.append({
                "id": opt_id,
                "prev_stock": cur_stock
            })

        # 영향받은 행이 0개면 롤백 처리
        if stock_exhausted:
            # 롤백: 1) 앞서 차감했던 옵션 재고 복구
            for dec in decremented_records:
                try:
                    admin.table("product_options").update({
                        "stock": dec["prev_stock"],
                        "stock_quantity": dec["prev_stock"]
                    }).eq("id", dec["id"]).execute()
                except Exception as rollback_err:
                    print(f"[경고] 재고 복구 오류: {rollback_err}", file=sys.stderr)

            # 롤백: 2) order_items 삭제
            if order_id:
                try:
                    admin.table("order_items").delete().eq("order_id", order_id).execute()
                except Exception:
                    pass

                # 롤백: 3) orders 삭제
                try:
                    admin.table("orders").delete().eq("id", order_id).execute()
                except Exception:
                    pass

            return False, "방금 재고가 소진되었습니다", None

        # ----------------------------------------------------------------------
        # 7. carts 아이템 DELETE
        # ----------------------------------------------------------------------
        admin.table("carts").delete().eq("user_id", user_id).execute()

        # 프로필 기본 배송지 동기화 (선택적)
        try:
            admin.table("profiles").update({"address": shipping_address}).eq("id", user_id).execute()
        except Exception:
            pass

        # ----------------------------------------------------------------------
        # 8. /order/complete/<order_id> 리다이렉트를 위한 order_id 반환
        # ----------------------------------------------------------------------
        return True, "주문 및 결제가 성공적으로 완료되었습니다.", order_id

    except Exception as e:
        print(f"[에러] 주문 생성 중 예외 발생: {e}", file=sys.stderr)
        # 예외 발생 시 생성된 주문 롤백
        if order_id:
            try:
                admin.table("order_items").delete().eq("order_id", order_id).execute()
                admin.table("orders").delete().eq("id", order_id).execute()
            except Exception:
                pass
        return False, f"주문 처리 중 오류가 발생했습니다: {str(e)}", None


def get_order_by_identifier(identifier: str, user_id: str = None) -> dict:
    """
    order_id (UUID) 또는 order_number로 주문 상세 내역 및 주문 품목 조회
    """
    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin or not identifier:
        return {}

    try:
        order = None

        # 1. UUID 형식인 경우 id로 먼저 조회
        if is_valid_uuid(identifier):
            query = admin.table("orders").select("*").eq("id", identifier)
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.execute()
            if res.data and len(res.data) > 0:
                order = res.data[0]

        # 2. id로 못 찾았거나 UUID가 아닌 경우 order_number로 조회
        if not order:
            query = admin.table("orders").select("*").eq("order_number", identifier)
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.execute()
            if res.data and len(res.data) > 0:
                order = res.data[0]

        if not order:
            return {}

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
        print(f"[에러] 주문 조회 실패 ({identifier}): {e}", file=sys.stderr)
        return {}


def get_order_by_number(order_number: str, user_id: str = None) -> dict:
    """하위 호환성을 위한 함수 래퍼"""
    return get_order_by_identifier(order_number, user_id=user_id)
