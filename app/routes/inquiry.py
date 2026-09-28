"""
문의게시판(Inquiry) 블루프린트 라우트
- GET /inquiries : 문의 목록 페이지
- GET /inquiries/new : 문의 작성 페이지
- POST /inquiries/new : 문의 등록 처리 (비밀번호 필수)
- GET /inquiries/<id> : 문의 상세 페이지 (비밀글인 경우 비밀번호 확인 필요)
- POST /inquiries/<id>/verify : 비밀번호 검증 처리 (세션에 권한 부여)
- POST /inquiries/<id>/delete : 문의글 삭제 처리
"""

import sys
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.routes.main import get_supabase_client
from app.services.inquiry_service import (
    get_inquiry_list,
    get_inquiry_by_id,
    verify_inquiry_password,
    create_inquiry,
    delete_inquiry
)

inquiry_bp = Blueprint("inquiry", __name__, url_prefix="/inquiries")

@inquiry_bp.route("/")
def list_inquiries():
    """문의 목록 조회"""
    supabase = get_supabase_client()
    inquiries = get_inquiry_list(supabase)
    
    # 세션에서 이미 비밀번호 확인을 마친 문의글 id 집합
    unlocked_ids = session.get("unlocked_inquiries", [])

    return render_template("inquiries/list.html", inquiries=inquiries, unlocked_ids=unlocked_ids)

@inquiry_bp.route("/new", methods=["GET", "POST"])
def new_inquiry():
    """문의 작성 (GET: 폼 페이지, POST: 신규 문의 저장)"""
    if request.method == "POST":
        category = request.form.get("category", "일반문의")
        title = request.form.get("title", "").strip()
        author_name = request.form.get("author_name", "").strip()
        password = request.form.get("password", "").strip()
        content = request.form.get("content", "").strip()
        is_secret = request.form.get("is_secret") == "on"

        # 필수 입력값 유효성 검사
        if not title or not author_name or not password or not content:
            flash("제목, 작성자명, 비밀번호, 문의 내용을 모두 입력해주세요.", "danger")
            return render_template("inquiries/form.html", form=request.form)

        if len(password) < 4:
            flash("비밀번호는 최소 4자리 이상 입력해주세요.", "warning")
            return render_template("inquiries/form.html", form=request.form)

        supabase = get_supabase_client()
        created = create_inquiry(
            supabase=supabase,
            category=category,
            title=title,
            author_name=author_name,
            password=password,
            content=content,
            is_secret=is_secret
        )

        if created:
            # 본인이 작성한 글은 바로 열람할 수 있도록 세션에 등록
            unlocked = session.get("unlocked_inquiries", [])
            unlocked.append(created["id"])
            session["unlocked_inquiries"] = unlocked
            flash("문의가 성공적으로 등록되었습니다.", "success")
            return redirect(url_for("inquiry.detail_inquiry", inquiry_id=created["id"]))
        else:
            flash("문의 등록 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", "danger")
            return render_template("inquiries/form.html", form=request.form)

    return render_template("inquiries/form.html", form={})

@inquiry_bp.route("/<inquiry_id>")
def detail_inquiry(inquiry_id):
    """문의 상세 보기 (비밀글인 경우 비밀번호 확인 여부 체크)"""
    supabase = get_supabase_client()
    inquiry = get_inquiry_by_id(supabase, inquiry_id)

    if not inquiry:
        flash("존재하지 않거나 삭제된 문의글입니다.", "danger")
        return redirect(url_for("inquiry.list_inquiries"))

    # 비밀글 체크
    unlocked_ids = session.get("unlocked_inquiries", [])
    if inquiry.get("is_secret") and inquiry_id not in unlocked_ids:
        # 비밀번호 입력 화면으로 안내
        return render_template("inquiries/verify.html", inquiry=inquiry)

    return render_template("inquiries/detail.html", inquiry=inquiry)

@inquiry_bp.route("/<inquiry_id>/verify", methods=["POST"])
def verify_inquiry(inquiry_id):
    """비밀글 비밀번호 검증 처리"""
    supabase = get_supabase_client()
    inquiry = get_inquiry_by_id(supabase, inquiry_id)

    if not inquiry:
        flash("문의글을 찾을 수 없습니다.", "danger")
        return redirect(url_for("inquiry.list_inquiries"))

    input_password = request.form.get("password", "").strip()

    if verify_inquiry_password(inquiry, input_password):
        # 인증 성공 시 세션에 추가
        unlocked = session.get("unlocked_inquiries", [])
        if inquiry_id not in unlocked:
            unlocked.append(inquiry_id)
            session["unlocked_inquiries"] = unlocked
        return redirect(url_for("inquiry.detail_inquiry", inquiry_id=inquiry_id))
    else:
        flash("비밀번호가 일치하지 않습니다. 다시 입력해주세요.", "danger")
        return render_template("inquiries/verify.html", inquiry=inquiry)

@inquiry_bp.route("/<inquiry_id>/delete", methods=["POST"])
def remove_inquiry(inquiry_id):
    """문의글 삭제 (비밀번호 일치 확인 후 처리)"""
    supabase = get_supabase_client()
    input_password = request.form.get("password", "").strip()

    success, msg = delete_inquiry(supabase, inquiry_id, input_password)
    if success:
        flash(msg, "success")
        # 세션 잠금 목록에서 제거
        unlocked = session.get("unlocked_inquiries", [])
        if inquiry_id in unlocked:
            unlocked.remove(inquiry_id)
            session["unlocked_inquiries"] = unlocked
    else:
        flash(msg, "danger")

    return redirect(url_for("inquiry.list_inquiries"))
