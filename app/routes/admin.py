"""
관리자 백오피스 라우트 모듈 (admin.py)
- 대시보드, 상품 관리, 주문 관리, 사용자 관리, 문의 관리, 매출 리포트
- admin_required 데코레이터로 관리자 권한 확인
"""

import sys
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, abort
from app.services.supabase_client import get_supabase_client, get_admin_supabase_client
from app.services.auth_service import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """
    [백오피스 대시보드]
    - 주요 통계: 매출, 주문, 사용자
    - 최근 주문, 인기 상품
    """
    supabase = get_admin_supabase_client() or get_supabase_client()
    
    # 기본 통계
    stats = {
        "total_orders": 0,
        "total_revenue": 0,
        "total_users": 0,
        "today_revenue": 0
    }
    
    # 최근 주문 초기화
    recent_orders = []
    
    try:
        # 전체 주문 수
        orders_res = supabase.table("orders").select("id").execute()
        stats["total_orders"] = len(orders_res.data) if orders_res.data else 0
        
        # 전체 사용자 수
        users_res = supabase.table("profiles").select("id").execute()
        stats["total_users"] = len(users_res.data) if users_res.data else 0
        
        # 전체 매출 및 오늘 매출 (final_amount 사용, 폴백으로 total_amount / total_price 지원)
        orders_detail_res = supabase.table("orders").select("id, final_amount, total_amount, created_at").execute()
        if orders_detail_res.data:
            stats["total_revenue"] = sum(
                int(o.get("final_amount") or o.get("total_amount") or o.get("total_price") or 0)
                for o in orders_detail_res.data
            )
            
            # 오늘 매출 계산
            today = datetime.utcnow().date()
            today_orders = [
                o for o in orders_detail_res.data
                if o.get("created_at") and datetime.fromisoformat(o.get("created_at", "").replace("Z", "+00:00")).date() == today
            ]
            stats["today_revenue"] = sum(
                int(o.get("final_amount") or o.get("total_amount") or o.get("total_price") or 0)
                for o in today_orders
            )
        
        # 최근 주문 5개
        recent_orders_res = supabase.table("orders").select(
            "id, order_number, user_id, final_amount, total_amount, status, created_at, profiles(full_name)"
        ).order("created_at", desc=True).limit(5).execute()
        
        recent_orders = []
        if recent_orders_res.data:
            for order in recent_orders_res.data:
                profile = order.get("profiles", {})
                user_name = profile.get("full_name") if isinstance(profile, dict) else None
                if not user_name:
                    user_name = order.get("recipient_name") or "고객"
                amount = int(order.get("final_amount") or order.get("total_amount") or order.get("total_price") or 0)
                display_num = order.get("order_number") or order.get("id")[:8]
                recent_orders.append({
                    "id": display_num,
                    "order_id": order.get("id"),
                    "user_name": user_name,
                    "total_price": f"{amount:,}원",
                    "status": order.get("status", "PAID"),
                    "created_at": order.get("created_at", "")
                })
        
    except Exception as e:
        print(f"[에러] 대시보드 통계 조회 실패: {e}", file=sys.stderr)
    
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_orders=recent_orders
    )


@admin_bp.route("/products")
@admin_required
def products():
    """
    [상품 관리 페이지]
    - 전체 상품 목록 조회
    - 등록, 수정, 삭제 기능
    """
    supabase = get_supabase_client()
    
    page = request.args.get("page", 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    products_list = []
    total_count = 0
    
    try:
        # 전체 상품 수
        count_res = supabase.table("products").select("id").execute()
        total_count = len(count_res.data) if count_res.data else 0
        
        # 상품 목록 조회
        products_res = supabase.table("products").select(
            "id, name, price, discount_rate, is_active, created_at, categories(name)"
        ).order("created_at", desc=True).range(offset, offset + per_page - 1).execute()
        
        if products_res.data:
            for product in products_res.data:
                category = product.get("categories", {})
                products_list.append({
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "category": category.get("name", "-") if isinstance(category, dict) else "-",
                    "price": f"{int(product.get('price', 0)):,}원",
                    "discount_rate": int(product.get("discount_rate", 0)),
                    "is_active": "활성" if product.get("is_active") else "비활성",
                    "created_at": product.get("created_at", "")[:10]
                })
    
    except Exception as e:
        print(f"[에러] 상품 조회 실패: {e}", file=sys.stderr)
    
    total_pages = (total_count + per_page - 1) // per_page
    
    return render_template(
        "admin/products.html",
        products=products_list,
        page=page,
        total_pages=total_pages,
        total_count=total_count
    )


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
    """
    [상품 등록 페이지]
    """
    if request.method == "POST":
        try:
            admin = get_admin_supabase_client()
            if not admin:
                return redirect(url_for("admin.products", error="db_connection_failed"))
            
            # 상품 정보 수집
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            price = int(request.form.get("price", 0))
            discount_rate = float(request.form.get("discount_rate", 0))
            category_id = request.form.get("category_id")
            
            if not name or price <= 0:
                return redirect(url_for("admin.product_new", error="invalid_data"))
            
            # 상품 등록
            res = admin.table("products").insert({
                "name": name,
                "description": description,
                "price": price,
                "discount_rate": discount_rate,
                "category_id": category_id if category_id else None,
                "is_active": True
            }).execute()
            
            if res.data:
                return redirect(url_for("admin.products", success="product_created"))
            else:
                return redirect(url_for("admin.product_new", error="creation_failed"))
        
        except Exception as e:
            print(f"[에러] 상품 등록 실패: {e}", file=sys.stderr)
            return redirect(url_for("admin.product_new", error="creation_failed"))
    
    # GET 요청: 카테고리 목록 조회
    supabase = get_supabase_client()
    categories = []
    
    try:
        cat_res = supabase.table("categories").select("id, name").eq("parent_id", None).execute()
        categories = cat_res.data if cat_res.data else []
    except Exception as e:
        print(f"[에러] 카테고리 조회 실패: {e}", file=sys.stderr)
    
    return render_template(
        "admin/product_form.html",
        categories=categories,
        product=None
    )


@admin_bp.route("/products/<product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
    """
    [상품 수정 페이지]
    """
    supabase = get_supabase_client()
    
    if request.method == "POST":
        try:
            admin = get_admin_supabase_client()
            if not admin:
                return redirect(url_for("admin.products", error="db_connection_failed"))
            
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            price = int(request.form.get("price", 0))
            discount_rate = float(request.form.get("discount_rate", 0))
            is_active = request.form.get("is_active") == "on"
            
            if not name or price <= 0:
                return redirect(url_for("admin.product_edit", product_id=product_id, error="invalid_data"))
            
            # 상품 수정
            admin.table("products").update({
                "name": name,
                "description": description,
                "price": price,
                "discount_rate": discount_rate,
                "is_active": is_active,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", product_id).execute()
            
            return redirect(url_for("admin.products", success="product_updated"))
        
        except Exception as e:
            print(f"[에러] 상품 수정 실패: {e}", file=sys.stderr)
            return redirect(url_for("admin.product_edit", product_id=product_id, error="update_failed"))
    
    # GET 요청: 상품 정보 조회
    product = None
    categories = []
    
    try:
        prod_res = supabase.table("products").select("*").eq("id", product_id).execute()
        if prod_res.data:
            product = prod_res.data[0]
        else:
            abort(404)
        
        cat_res = supabase.table("categories").select("id, name").execute()
        categories = cat_res.data if cat_res.data else []
    
    except Exception as e:
        print(f"[에러] 상품 조회 실패: {e}", file=sys.stderr)
        abort(404)
    
    return render_template(
        "admin/product_form.html",
        product=product,
        categories=categories
    )


@admin_bp.route("/products/<product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id):
    """
    [상품 삭제]
    """
    try:
        admin = get_admin_supabase_client()
        if not admin:
            return jsonify({"success": False, "message": "데이터베이스 연결 실패"}), 500
        
        admin.table("products").delete().eq("id", product_id).execute()
        return jsonify({"success": True, "message": "상품이 삭제되었습니다."})
    
    except Exception as e:
        print(f"[에러] 상품 삭제 실패: {e}", file=sys.stderr)
        return jsonify({"success": False, "message": "삭제 실패"}), 500


@admin_bp.route("/inventory", methods=["GET"])
@admin_required
def inventory():
    """
    [재고 관리 페이지]
    - 전체 상품 옵션별 실시간 재고 현황 조회
    - 재고 부족/품절 필터링 및 상품명 검색
    - 옵션별 재고 수량 실시간 수정
    """
    supabase = get_admin_supabase_client() or get_supabase_client()
    
    status_filter = request.args.get("status", "all")  # all, out_of_stock, low_stock, normal
    search_query = request.args.get("q", "").strip()
    
    inventory_items = []
    summary_stats = {
        "total_options": 0,
        "out_of_stock": 0,
        "low_stock": 0,
        "normal_stock": 0,
        "total_stock_count": 0
    }

    try:
        # 옵션 및 상품 기본 정보 JOIN 조회
        query = supabase.table("product_options").select(
            "id, product_id, color, size, additional_price, stock, stock_quantity, sku, products(id, name, price, is_active)"
        )
        
        res = query.execute()
        raw_items = res.data or []

        for item in raw_items:
            product = item.get("products") or {}
            product_name = product.get("name") or "이름 없는 상품"
            
            # 검색어 필터링
            if search_query:
                sku_val = (item.get("sku") or "").lower()
                color_val = (item.get("color") or "").lower()
                size_val = (item.get("size") or "").lower()
                query_lower = search_query.lower()
                if (query_lower not in product_name.lower() and 
                    query_lower not in sku_val and 
                    query_lower not in color_val and 
                    query_lower not in size_val):
                    continue

            # 재고 수량 계산 (stock 또는 stock_quantity)
            stock_val = item.get("stock")
            if stock_val is None:
                stock_val = item.get("stock_quantity") or 0
            stock_val = max(0, int(stock_val))

            # 상태 분류 (0: 품절, 1~5: 재고부족, 6이상: 정상)
            if stock_val == 0:
                item_status = "out_of_stock"
                status_label = "품절"
                status_badge = "danger"
                summary_stats["out_of_stock"] += 1
            elif stock_val <= 5:
                item_status = "low_stock"
                status_label = "재고부족"
                status_badge = "warning"
                summary_stats["low_stock"] += 1
            else:
                item_status = "normal"
                status_label = "정상"
                status_badge = "success"
                summary_stats["normal_stock"] += 1

            summary_stats["total_options"] += 1
            summary_stats["total_stock_count"] += stock_val

            # 필터 적용
            if status_filter == "out_of_stock" and item_status != "out_of_stock":
                continue
            if status_filter == "low_stock" and item_status != "low_stock":
                continue
            if status_filter == "normal" and item_status != "normal":
                continue

            inventory_items.append({
                "id": item.get("id"),
                "product_id": item.get("product_id"),
                "product_name": product_name,
                "product_price": f"{int(product.get('price', 0)):,}원",
                "is_active": product.get("is_active", True),
                "color": item.get("color") or "-",
                "size": item.get("size") or "-",
                "sku": item.get("sku") or "-",
                "stock": stock_val,
                "status": item_status,
                "status_label": status_label,
                "status_badge": status_badge,
            })

    except Exception as e:
        print(f"[에러] 재고 목록 조회 실패: {e}", file=sys.stderr)

    return render_template(
        "admin/inventory.html",
        items=inventory_items,
        summary=summary_stats,
        status_filter=status_filter,
        search_query=search_query
    )


@admin_bp.route("/inventory/<option_id>/update", methods=["POST"])
@admin_required
def inventory_update(option_id):
    """
    [옵션 재고 수량 단건 수정 API]
    - 입력받은 수량(양수/0)으로 stock 및 stock_quantity 업데이트
    """
    try:
        admin = get_admin_supabase_client() or get_supabase_client()
        if not admin:
            return jsonify({"success": False, "message": "데이터베이스 연결에 실패했습니다."}), 500

        data = request.get_json(silent=True) or request.form or {}
        new_stock = data.get("stock")

        if new_stock is None:
            return jsonify({"success": False, "message": "재고 수량을 입력해주세요."}), 400

        try:
            new_stock = int(new_stock)
            if new_stock < 0:
                return jsonify({"success": False, "message": "재고는 0개 이상이어야 합니다."}), 400
        except ValueError:
            return jsonify({"success": False, "message": "올바른 숫자를 입력해주세요."}), 400

        # product_options 테이블 stock, stock_quantity 동시 갱신
        res = admin.table("product_options").update({
            "stock": new_stock,
            "stock_quantity": new_stock
        }).eq("id", option_id).execute()

        if not res.data:
            return jsonify({"success": False, "message": "해당 옵션을 찾을 수 없습니다."}), 404

        return jsonify({
            "success": True,
            "message": f"재고가 {new_stock}개로 수정되었습니다.",
            "new_stock": new_stock
        })

    except Exception as e:
        print(f"[에러] 재고 수정 실패: {e}", file=sys.stderr)
        return jsonify({"success": False, "message": f"재고 수정 중 오류 발생: {str(e)}"}), 500


@admin_bp.route("/orders")
@admin_required
def orders():
    """
    [주문 관리 페이지]
    - 전체 주문 목록 조회
    - 배송 상태 업데이트
    """
    supabase = get_admin_supabase_client() or get_supabase_client()
    
    page = request.args.get("page", 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    orders_list = []
    total_count = 0
    
    try:
        # 전체 주문 수
        count_res = supabase.table("orders").select("id").execute()
        total_count = len(count_res.data) if count_res.data else 0
        
        # 주문 목록 (final_amount, recipient_name, recipient_phone 등 orders 테이블 컬럼 활용)
        orders_res = supabase.table("orders").select(
            "id, order_number, user_id, final_amount, total_amount, status, recipient_name, recipient_phone, shipping_address, created_at, profiles(full_name, phone_number)"
        ).order("created_at", desc=True).range(offset, offset + per_page - 1).execute()
        
        if orders_res.data:
            for order in orders_res.data:
                profile = order.get("profiles", {})
                user_name = profile.get("full_name") if isinstance(profile, dict) else None
                if not user_name:
                    user_name = order.get("recipient_name") or "-"
                
                phone = profile.get("phone_number") if isinstance(profile, dict) else None
                if not phone:
                    phone = order.get("recipient_phone") or "-"

                amount = int(order.get("final_amount") or order.get("total_amount") or order.get("total_price") or 0)
                display_num = order.get("order_number") or order.get("id")[:8]

                orders_list.append({
                    "id": display_num,
                    "order_id": order.get("id"),
                    "user_name": user_name,
                    "phone": phone,
                    "total_price": f"{amount:,}원",
                    "status": order.get("status", "PAID"),
                    "created_at": order.get("created_at", "")[:10]
                })
    
    except Exception as e:
        print(f"[에러] 주문 조회 실패: {e}", file=sys.stderr)
    
    total_pages = (total_count + per_page - 1) // per_page
    
    return render_template(
        "admin/orders.html",
        orders=orders_list,
        page=page,
        total_pages=total_pages,
        total_count=total_count
    )


@admin_bp.route("/users")
@admin_required
def users():
    """
    [사용자 관리 페이지]
    - 전체 사용자 목록 조회
    - 검색 및 등급 필터링
    """
    supabase = get_admin_supabase_client() or get_supabase_client()
    
    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("q", "").strip()
    grade_filter = request.args.get("grade", "all").strip()
    per_page = 20
    offset = (page - 1) * per_page
    
    users_list = []
    total_count = 0
    current_user_id = session.get("user_id")
    
    try:
        # 사용자 목록 조회
        users_res = supabase.table("profiles").select(
            "id, email, full_name, phone_number, grade, role, total_spent, created_at"
        ).order("created_at", desc=True).execute()
        
        all_users = users_res.data or []
        
        # 검색 및 등급 필터링
        filtered_users = []
        for user in all_users:
            if grade_filter != "all" and user.get("grade") != grade_filter:
                continue
            if search_query:
                q_lower = search_query.lower()
                email = (user.get("email") or "").lower()
                name = (user.get("full_name") or "").lower()
                phone = (user.get("phone_number") or "").lower()
                if q_lower not in email and q_lower not in name and q_lower not in phone:
                    continue
            filtered_users.append(user)
            
        total_count = len(filtered_users)
        paged_users = filtered_users[offset : offset + per_page]
        
        for user in paged_users:
            user_id = str(user.get("id"))
            users_list.append({
                "full_id": user_id,
                "id": user_id[:8],
                "email": user.get("email", "-"),
                "full_name": user.get("full_name", "-"),
                "phone": user.get("phone_number", "-"),
                "grade": user.get("grade", "-"),
                "role": "관리자" if user.get("role") == "admin" else "사용자",
                "total_spent": f"{int(user.get('total_spent', 0)):,}원",
                "joined": user.get("created_at", "")[:10],
                "is_self": bool(current_user_id and user_id == str(current_user_id))
            })
    
    except Exception as e:
        print(f"[에러] 사용자 조회 실패: {e}", file=sys.stderr)
    
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    
    return render_template(
        "admin/users.html",
        users=users_list,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        search_query=search_query,
        grade_filter=grade_filter
    )


@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@admin_required
def user_delete(user_id):
    """
    [회원 탈퇴 (삭제) 처리 API]
    - 관리자가 특정 사용자를 강제 탈퇴 처리
    - 본인 관리자 계정은 탈퇴 불가
    - Supabase auth.users 및 profiles 테이블에서 완전 삭제
    """
    current_admin_id = session.get("user_id")
    if current_admin_id and str(user_id) == str(current_admin_id):
        return jsonify({
            "success": False,
            "message": "현재 로그인된 본인 관리자 계정은 탈퇴할 수 없습니다."
        }), 400

    admin = get_admin_supabase_client()
    if not admin:
        return jsonify({"success": False, "message": "데이터베이스 연결에 실패했습니다."}), 500

    try:
        # 삭제 대상 사용자 정보 조회
        target_name = "사용자"
        profile_res = admin.table("profiles").select("id, email, full_name, role").eq("id", user_id).execute()
        if profile_res.data and len(profile_res.data) > 0:
            target_user = profile_res.data[0]
            target_name = target_user.get("full_name") or target_user.get("email") or "사용자"

        # 1. Supabase Auth에서 사용자 삭제 (cascade로 profiles 등 연계 처리)
        auth_success = False
        try:
            admin.auth.admin.delete_user(user_id)
            auth_success = True
        except Exception as auth_err:
            print(f"[경고] Auth 사용자 삭제 중 오류: {auth_err}", file=sys.stderr)

        # 2. profiles 테이블에서도 확실히 삭제 (auth 계정이 없거나 별도 프로필인 경우)
        try:
            admin.table("profiles").delete().eq("id", user_id).execute()
        except Exception as prof_err:
            print(f"[경고] profiles 레코드 삭제 중 오류: {prof_err}", file=sys.stderr)

        return jsonify({
            "success": True,
            "message": f"'{target_name}' 회원이 성공적으로 탈퇴 처리되었습니다."
        })

    except Exception as e:
        print(f"[에러] 회원 탈퇴 처리 실패: {e}", file=sys.stderr)
        return jsonify({
            "success": False,
            "message": f"회원 탈퇴 처리 중 오류가 발생했습니다: {str(e)}"
        }), 500


@admin_bp.route("/inquiries")
@admin_required
def inquiries():
    """
    [문의 관리 페이지]
    - 전체 문의 목록 조회
    - 답변 여부 확인
    """
    supabase = get_supabase_client()
    
    page = request.args.get("page", 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    inquiries_list = []
    total_count = 0
    
    try:
        # 전체 문의 수
        count_res = supabase.table("inquiries").select("id").execute()
        total_count = len(count_res.data) if count_res.data else 0
        
        # 문의 목록
        inquiries_res = supabase.table("inquiries").select(
            "id, title, category, status, created_at, profiles(full_name)"
        ).order("created_at", desc=True).range(offset, offset + per_page - 1).execute()
        
        if inquiries_res.data:
            for inquiry in inquiries_res.data:
                profile = inquiry.get("profiles", {})
                inquiries_list.append({
                    "id": inquiry.get("id")[:8],
                    "title": inquiry.get("title", "-")[:50],
                    "category": inquiry.get("category", "-"),
                    "user_name": profile.get("full_name", "-") if isinstance(profile, dict) else "-",
                    "status": "답변됨" if inquiry.get("status") == "answered" else "미답변",
                    "created_at": inquiry.get("created_at", "")[:10]
                })
    
    except Exception as e:
        print(f"[에러] 문의 조회 실패: {e}", file=sys.stderr)
    
    total_pages = (total_count + per_page - 1) // per_page
    
    return render_template(
        "admin/inquiries.html",
        inquiries=inquiries_list,
        page=page,
        total_pages=total_pages,
        total_count=total_count
    )


@admin_bp.route("/reports")
@admin_required
def reports():
    """
    [매출 리포트 페이지]
    - 일일/월별 매출 통계
    """
    supabase = get_admin_supabase_client() or get_supabase_client()
    
    # 기간 선택
    report_type = request.args.get("type", "daily")  # daily, monthly
    
    sales_data = []
    
    try:
        orders_res = supabase.table("orders").select("id, final_amount, total_amount, created_at").execute()
        
        if orders_res.data:
            if report_type == "daily":
                # 최근 30일 일일 매출
                sales_by_date = {}
                for order in orders_res.data:
                    date = order.get("created_at", "")[:10]
                    price = int(order.get("final_amount") or order.get("total_amount") or order.get("total_price") or 0)
                    sales_by_date[date] = sales_by_date.get(date, 0) + price
                
                # 최근 30일 데이터만
                thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).date()
                for date in sorted(sales_by_date.keys()):
                    if datetime.fromisoformat(date).date() >= thirty_days_ago:
                        sales_data.append({
                            "date": date,
                            "sales": sales_by_date[date],
                            "sales_str": f"{sales_by_date[date]:,}원"
                        })
            
            else:  # monthly
                # 월별 매출
                sales_by_month = {}
                for order in orders_res.data:
                    month = order.get("created_at", "")[:7]
                    price = int(order.get("final_amount") or order.get("total_amount") or order.get("total_price") or 0)
                    sales_by_month[month] = sales_by_month.get(month, 0) + price
                
                for month in sorted(sales_by_month.keys()):
                    sales_data.append({
                        "date": month,
                        "sales": sales_by_month[month],
                        "sales_str": f"{sales_by_month[month]:,}원"
                    })
    
    except Exception as e:
        print(f"[에러] 매출 리포트 조회 실패: {e}", file=sys.stderr)
    
    return render_template(
        "admin/reports.html",
        sales_data=sales_data,
        report_type=report_type
    )
