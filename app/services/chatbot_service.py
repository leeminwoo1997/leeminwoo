"""
챗봇 서비스 모듈
- 규칙 기반 챗봇 응답 생성
- 자주 묻는 질문(FAQ) 응답
- 상품 관련 문의 처리
- Young Style 2026 S/S 컬렉션 기반
"""

import re
from datetime import datetime

# ===============================================
# 챗봇 규칙 기반 응답 데이터베이스
# ===============================================

# 자주 묻는 질문 및 답변
FAQ_RESPONSES = {
    "배송": [
        "🚚 배송 정보",
        "• 50,000원 이상: 무료배송",
        "• 50,000원 미만: 배송비 3,000원",
        "• 배송 기간: 주문 후 2-3일 이내 배송 시작",
        "• 배송사: CJ대한통운, 로젠, 우체국 중 선택 가능"
    ],
    "반품": [
        "🔄 반품/환불 정책",
        "• 반품 기간: 상품 수령일로부터 7일 이내",
        "• 반품 조건: 미착용, 미개봉 상태",
        "• 반품 배송비: 고객 부담 (불량/오배송 제외)",
        "• 환불: 반품 수령 후 3-5일 내 처리"
    ],
    "결제": [
        "💳 결제 방법",
        "• 신용카드 (무이자 할부 최대 12개월)",
        "• 체크카드",
        "• 계좌이체",
        "• 휴대폰 결제",
        "• 모든 결제는 SSL 암호화로 안전합니다"
    ],
    "멤버십": [
        "⭐ 회원 혜택",
        "• 신규 회원: 첫 주문 10% 할인",
        "• 계절 세일: 현재 S/S 50% 할인 진행 중",
        "• 정기 이벤트: 매달 다양한 쿠폰 제공",
        "• 뉴스레터: 최신 상품 정보와 할인 소식"
    ],
    "상품": [
        "🛍️ Young Style 2026 S/S 신상품",
        "• 베이직 크루 티셔츠 - 29,900원",
        "• 와이드 데님 팬츠 - 39,900원",
        "• 오버핏 쿠프 자켓 - 59,900원",
        "• 플로럴 미디 원피스 - 45,900원",
        "더 많은 상품은 '신상품' 탭에서 확인하세요!"
    ],
    "주문": [
        "📦 주문 관련",
        "• 주문 조회: 마이페이지 > 주문 내역",
        "• 주문 취소: 배송 전에만 가능",
        "• 주문 변경: 배송 전에만 가능",
        "• 배송 시작 후는 반품으로 처리됩니다"
    ],
    "회원가입": [
        "👤 회원가입 안내",
        "• 회원가입: 홈페이지 우측 상단 또는 로그인 페이지",
        "• 신규 회원 혜택: 첫 주문 10% 할인쿠폰",
        "• 가입은 무료이며 회원만의 특별한 혜택이 있습니다",
        "• 언제든지 회원 탈퇴 가능"
    ],
    "사이즈": [
        "👕 사이즈 가이드",
        "• XS: 155-160cm",
        "• S: 160-165cm",
        "• M: 165-170cm",
        "• L: 170-175cm",
        "• XL: 175-180cm",
        "정확한 사이즈 선택은 각 상품의 상세 정보에서 확인하세요!"
    ],
    "할인": [
        "🎉 할인/쿠폰 정보",
        "• 신규 회원: 첫 주문 10% 할인",
        "• 현재 프로모션: 2026 S/S 최대 50% 할인",
        "• 쿠폰 적용: 결제 단계에서 자동 적용",
        "• 뉴스레터 구독으로 추가 할인 받으세요!"
    ]
}

# 인사말 및 기본 응답
GREETING_KEYWORDS = ["안녕하세요", "안녕하세요!", "안녕", "하이", "hi", "hello", "반갑", "식사했어"]
FAREWELL_KEYWORDS = ["잘가", "바이", "bye", "뿐", "나중에"]

def get_chatbot_response(user_message: str) -> dict:
    """
    사용자 메시지를 받아 챗봇 응답을 생성합니다.
    
    Args:
        user_message: 사용자가 입력한 메시지
        
    Returns:
        {
            "type": "text",
            "content": "응답 메시지"
        }
    """
    
    # 메시지 전처리 (공백 제거, 소문자 변환)
    cleaned_msg = user_message.strip().lower()
    
    # 1. 인사말 감지
    if any(keyword in cleaned_msg for keyword in GREETING_KEYWORDS):
        return {
            "type": "text",
            "content": "안녕하세요! 👋 Young Style 챗봇입니다.\n어떤 도움을 드릴까요?\n\n아래 주제에서 선택하거나 직접 질문해주세요:\n• 배송 정보\n• 반품/환불\n• 상품 추천\n• 주문 조회\n• 회원가입\n• 사이즈 가이드"
        }
    
    # 2. 인사말 (작별) 감지 - "안녕"이 포함된 경우 확인
    if "잘가" in cleaned_msg or "바이" in cleaned_msg or "bye" in cleaned_msg or ("안녕" in cleaned_msg and ("히" in cleaned_msg or len(cleaned_msg) < 10)):
        return {
            "type": "text",
            "content": "감사합니다! 😊\nYoung Style을 이용해주셔서 감사합니다.\n다시 찾아뵙겠습니다! 👋"
        }
    
    # 3. FAQ 키워드 매칭 (가장 일치하는 항목 찾기)
    best_match = None
    best_score = 0
    
    for keyword, response in FAQ_RESPONSES.items():
        # 키워드가 메시지에 포함되는 정도를 계산
        keyword_score = 0
        
        # 정확한 키워드 매칭
        if keyword in cleaned_msg:
            keyword_score = 100
        else:
            # 부분 매칭 (한글 자모 분해하지 않고 그대로 비교)
            for char in keyword:
                if char in cleaned_msg:
                    keyword_score += 20
        
        if keyword_score > best_score:
            best_score = keyword_score
            best_match = response
    
    # 높은 점수의 매칭이 있으면 반환
    if best_match and best_score >= 40:
        return {
            "type": "text",
            "content": "\n".join(best_match)
        }
    
    # 4. 기본 응답 (매칭되는 키워드가 없는 경우)
    return {
        "type": "text",
        "content": f"죄송합니다. '{user_message}'에 대해 정확히 이해하지 못했습니다.\n\n자주 묻는 질문:\n• 배송비는 얼마인가요?\n• 반품은 어떻게 하나요?\n• 신상품을 추천해줄 수 있나요?\n• 주문을 취소하고 싶어요\n• 사이즈는 어떻게 선택하나요?\n\n더 자세한 사항은 고객센터(010-1234-5678)로 연락주세요!"
    }

def get_quick_replies() -> list:
    """빠른 응답 버튼 목록"""
    return [
        {"label": "🚚 배송 정보", "action": "배송"},
        {"label": "🔄 반품/환불", "action": "반품"},
        {"label": "💳 결제 방법", "action": "결제"},
        {"label": "👤 회원가입", "action": "회원가입"},
        {"label": "🛍️ 상품 추천", "action": "상품"},
        {"label": "👕 사이즈 가이드", "action": "사이즈"},
        {"label": "🎉 할인/쿠폰", "action": "할인"}
    ]

def format_chat_message(user_id: str, sender_type: str, content: str, message_id: str = None) -> dict:
    """
    채팅 메시지를 표준 포맷으로 변환합니다.
    
    Args:
        user_id: 사용자 ID
        sender_type: "user" 또는 "bot"
        content: 메시지 내용
        message_id: 메시지 ID (DB 저장용)
        
    Returns:
        표준화된 메시지 객체
    """
    return {
        "id": message_id,
        "user_id": user_id,
        "sender_type": sender_type,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
        "is_read": False
    }
