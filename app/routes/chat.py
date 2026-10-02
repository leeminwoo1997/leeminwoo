"""
챗봇 라우트 블루프린트
- GET /chat/api/messages : 채팅 히스토리 조회
- POST /chat/api/messages : 메시지 전송 및 챗봇 응답
- POST /chat/api/quick-replies : 빠른 응답 버튼 목록 조회
"""

import sys
from flask import Blueprint, request, jsonify, session
from app.services.supabase_client import get_supabase_client, get_admin_supabase_client
from app.services.chatbot_service import get_chatbot_response, get_quick_replies

chat_bp = Blueprint("chat", __name__, url_prefix="/chat/api")

@chat_bp.route("/messages", methods=["GET"])
def get_messages():
    """
    현재 사용자의 채팅 히스토리 조회
    - 로그인하지 않은 사용자는 session_id 기반 임시 채팅
    - 로그인한 사용자는 user_id 기반 영구 저장
    """
    user_id = session.get("user_id")
    
    if not user_id:
        # 로그인하지 않은 사용자: 세션 기반 임시 채팅
        chat_history = session.get("chat_history", [])
        return jsonify({
            "messages": chat_history,
            "is_guest": True
        })
    
    admin = get_admin_supabase_client() or get_supabase_client()
    if not admin:
        return jsonify({"success": False, "message": "데이터베이스 연결 실패"}), 500
    
    try:
        # 사용자의 채팅 기록 조회 (최근 50개)
        res = admin.table("chat_messages").select("*").eq("user_id", user_id).order("created_at", desc=False).limit(50).execute()
        
        messages = []
        if res.data:
            for msg in res.data:
                messages.append({
                    "id": msg["id"],
                    "sender_type": msg["sender_type"],
                    "content": msg["content"],
                    "timestamp": msg["created_at"],
                    "is_read": msg["is_read"]
                })
        
        return jsonify({
            "messages": messages,
            "is_guest": False
        })
    
    except Exception as e:
        print(f"[에러] 채팅 히스토리 조회 실패: {e}", file=sys.stderr)
        return jsonify({"success": False, "message": "채팅 조회 실패"}), 500


@chat_bp.route("/messages", methods=["POST"])
def send_message():
    """
    사용자 메시지를 받아 저장하고 챗봇 응답 생성
    
    Request JSON:
    {
        "content": "사용자 메시지"
    }
    
    Response:
    {
        "success": true,
        "user_message": {...},
        "bot_response": {...}
    }
    """
    data = request.get_json() or {}
    user_message = data.get("content", "").strip()
    
    if not user_message:
        return jsonify({"success": False, "message": "메시지가 비어있습니다"}), 400
    
    user_id = session.get("user_id")
    
    # 사용자 메시지 저장
    try:
        if user_id:
            # 로그인한 사용자: DB에 저장
            admin = get_admin_supabase_client() or get_supabase_client()
            if admin:
                user_msg_res = admin.table("chat_messages").insert({
                    "user_id": user_id,
                    "sender_type": "user",
                    "content": user_message,
                    "is_read": True
                }).execute()
                user_msg_id = user_msg_res.data[0]["id"] if user_msg_res.data else None
            else:
                user_msg_id = None
        else:
            # 로그인하지 않은 사용자: 세션에만 저장
            if "chat_history" not in session:
                session["chat_history"] = []
            user_msg_id = f"temp-{len(session['chat_history'])}"
        
        # 챗봇 응답 생성
        bot_response_data = get_chatbot_response(user_message)
        bot_response_text = bot_response_data.get("content", "잠시만 기다려주세요...")
        
        # 챗봇 응답 저장
        if user_id:
            admin = get_admin_supabase_client() or get_supabase_client()
            if admin:
                bot_msg_res = admin.table("chat_messages").insert({
                    "user_id": user_id,
                    "sender_type": "bot",
                    "content": bot_response_text,
                    "is_read": False
                }).execute()
                bot_msg_id = bot_msg_res.data[0]["id"] if bot_msg_res.data else None
            else:
                bot_msg_id = None
        else:
            # 로그인하지 않은 사용자: 세션에만 저장
            bot_msg_id = f"temp-bot-{len(session['chat_history'])}"
        
        # 세션 업데이트 (로그인하지 않은 사용자)
        if not user_id:
            session["chat_history"].append({
                "id": user_msg_id,
                "sender_type": "user",
                "content": user_message,
                "timestamp": None
            })
            session["chat_history"].append({
                "id": bot_msg_id,
                "sender_type": "bot",
                "content": bot_response_text,
                "timestamp": None
            })
            session.modified = True
        
        return jsonify({
            "success": True,
            "user_message": {
                "id": user_msg_id,
                "sender_type": "user",
                "content": user_message
            },
            "bot_response": {
                "id": bot_msg_id,
                "sender_type": "bot",
                "content": bot_response_text
            }
        })
    
    except Exception as e:
        print(f"[에러] 메시지 전송 실패: {e}", file=sys.stderr)
        return jsonify({"success": False, "message": "메시지 전송 실패"}), 500


@chat_bp.route("/quick-replies", methods=["GET"])
def quick_replies():
    """빠른 응답 버튼 목록 반환"""
    return jsonify({
        "replies": get_quick_replies()
    })
