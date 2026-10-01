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
@admin_required
def dashboard():
    """
    [백오피스 대시보드]
    - 주요 통계: 매출, 주문, 사용자
    - 최근 주문, 인기 상품
    """
    supabase = get_supabase_client()
    
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
        
        # 전체 매출 및 오늘 매출
        orders_detail_res = supabase.table("orders").select("total_price, created_at").execute()
        if orders_detail_res.data:
            stats["total_revenue"] = sum(int(o.get("total_price", 0)) for o in orders_detail_res.data)
            
            # 오늘 매출 계산
            today = datetime.utcnow().date()
            today_orders = [
                o for o in orders_detail_res.data
                if datetime.fromisoformat(o.get("created_at", "").replace("Z", "+00:00")).date() == today
            ]
            stats["today_revenue"] = sum(int(o.get("total_price", 0)) for o in today_orders)
        
        # 최근 주문 5개
        recent_orders_res = supabase.table("orders").select(
            "id, user_id, total_price, status, created_at, profiles(full_name)"
        ).order("created_at", desc=True).limit(5).execute()
        
        recent_orders = []
        if recent_orders_res.data:
            for order in recent_orders_res.data:
                profile = order.get("profiles", {})
                recent_orders.append({
                    "id": order.get("id")[:8],
                    "user_name": profile.get("full_name", "확인안됨") if isinstance(profile, dict) else "확인안됨",
                    "total_price": f"{int(order.get('total_price', 0)):,}원",
                    "status": order.get("status", "pending"),
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


@admin_bp.route("/orders")
@admin_required
def orders():
    """
    [주문 관리 페이지]
    - 전체 주문 목록 조회
    - 배송 상태 업데이트
    """
    supabase = get_supabase_client()
    
    page = request.args.get("page", 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    orders_list = []
    total_count = 0
    
    try:
        # 전체 주문 수
        count_res = supabase.table("orders").select("id").execute()
        total_count = len(count_res.data) if count_res.data else 0
        
        # 주문 목록
        orders_res = supabase.table("orders").select(
            "id, user_id, total_price, status, created_at, profiles(full_name, phone_number)"
        ).order("created_at", desc=True).range(offset, offset + per_page - 1).execute()
        
        if orders_res.data:
            for order in orders_res.data:
                profile = order.get("profiles", {})
                orders_list.append({
                    "id": order.get("id")[:8],
                    "user_name": profile.get("full_name", "-") if isinstance(profile, dict) else "-",
                    "phone": profile.get("phone_number", "-") if isinstance(profile, dict) else "-",
                    "total_price": f"{int(order.get('total_price', 0)):,}원",
                    "status": order.get("status", "pending"),
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
    """
    supabase = get_supabase_client()
    
    page = request.args.get("page", 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    users_list = []
    total_count = 0
    
    try:
        # 전체 사용자 수
        count_res = supabase.table("profiles").select("id").execute()
        total_count = len(count_res.data) if count_res.data else 0
        
        # 사용자 목록
        users_res = supabase.table("profiles").select(
            "id, email, full_name, phone_number, grade, role, total_spent, created_at"
        ).order("created_at", desc=True).range(offset, offset + per_page - 1).execute()
        
        if users_res.data:
            for user in users_res.data:
                users_list.append({
                    "id": user.get("id")[:8],
                    "email": user.get("email", "-"),
                    "full_name": user.get("full_name", "-"),
                    "phone": user.get("phone_number", "-"),
                    "grade": user.get("grade", "-"),
                    "role": "관리자" if user.get("role") == "admin" else "사용자",
                    "total_spent": f"{int(user.get('total_spent', 0)):,}원",
                    "joined": user.get("created_at", "")[:10]
                })
    
    except Exception as e:
        print(f"[에러] 사용자 조회 실패: {e}", file=sys.stderr)
    
    total_pages = (total_count + per_page - 1) // per_page
    
    return render_template(
        "admin/users.html",
        users=users_list,
        page=page,
        total_pages=total_pages,
        total_count=total_count
    )


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
    supabase = get_supabase_client()
    
    # 기간 선택
    report_type = request.args.get("type", "daily")  # daily, monthly
    
    sales_data = []
    
    try:
        orders_res = supabase.table("orders").select("total_price, created_at").execute()
        
        if orders_res.data:
            if report_type == "daily":
                # 최근 30일 일일 매출
                sales_by_date = {}
                for order in orders_res.data:
                    date = order.get("created_at", "")[:10]
                    price = int(order.get("total_price", 0))
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
                    price = int(order.get("total_price", 0))
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
