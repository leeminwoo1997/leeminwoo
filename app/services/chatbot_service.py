"""
챗봇 서비스 모듈
- 규칙 기반 챗봇 응답 생성
- 자주 묻는 질문(FAQ) 응답
- 상품 관련 문의 처리
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
        "• 30,000원 이상 무료배송",
        "• 미만 시 배송비 3,000원",
        "• 일반 배송: 2-3일 소요"
    ],
    "반품": [
        "🔄 반품/환불 정책",
        "• 상품 수령 후 7일 이내 반품 가능",
        "• 미개봉 상태여야 함",
        "• 배송비는 고객 부담"
    ],
    "결제": [
        "💳 결제 방법",
        "• 신용카드",
        "• 체크카드", 
        "• 계좌이체",
        "• 무통장입금"
    ],
    "멤버십": [
        "⭐ 멤버십 등급",
        "• BRONZE: 기본 회원",
        "• SILVER: 누적 50만원 이상",
        "• GOLD: 누적 100만원 이상",
        "• VIP: 누적 200만원 이상"
    ],
    "문의": [
        "📧 고객센터",
        "• 문의게시판에서 질문 등록",
        "• 2시간 내 답변",
        "• 비밀글로 작성 가능"
    ],
    "사이즈": [
        "👕 사이즈 가이드",
        "• XS: 155-160cm",
        "• S: 160-165cm",
        "• M: 165-170cm",
        "• L: 170-175cm",
        "• XL: 175-180cm"
    ]
}

# 인사말 및 기본 응답
GREETING_KEYWORDS = ["안녕", "하이", "hi", "hello", "반갑", "식사했어"]
FAREWELL_KEYWORDS = ["잘가", "바이", "bye", "뿐", "나중에"]

def get_chatbot_response(user_message: str) -> dict:
    """
    사용자 메시지를 받아 챗봇 응답을 생성합니다.
    
    Args:
        user_message: 사용자가 입력한 메시지
        
    Returns:
        {
            "type": "text|options|link",
            "content": "응답 메시지",
            "options": [...],  # type이 'options'인 경우
            "link": {...}      # type이 'link'인 경우
        }
    """
    
    # 메시지 전처리 (공백 제거, 소문자 변환)
    cleaned_msg = user_message.strip().lower()
    
    # 1. 인사말 감지
    if any(keyword in cleaned_msg for keyword in GREETING_KEYWORDS):
        return {
            "type": "text",
            "content": "안녕하세요! 👋 Young Style 고객센터입니다.\n어떤 도움을 드릴까요?\n\n아래 버튼을 클릭하거나 직접 질문해주세요!"
        }
    
    # 2. 인사말 (작별) 감지
    if any(keyword in cleaned_msg for keyword in FAREWELL_KEYWORDS):
        return {
            "type": "text",
            "content": "감사합니다! 😊\nYoung Style을 이용해주셔서 감사합니다.\n다시 찾아뵙겠습니다! 👋"
        }
    
    # 3. FAQ 키워드 매칭
    for keyword, response in FAQ_RESPONSES.items():
        if keyword in cleaned_msg:
            return {
                "type": "text",
                "content": "\n".join(response)
            }
    
    # 4. 상품 관련 질문 감지
    if any(word in cleaned_msg for word in ["상품", "제품", "옷", "가격", "가격이"]):
        return {
            "type": "text",
            "content": "🛍️ 상품에 대해 궁금하신 사항이 있으신가요?\n\n홈페이지의 '신상품' 또는 '베스트' 탭에서 원하는 상품을 찾아보세요.\n\n더 자세한 문의는 '문의게시판'에서 질문해주세요!"
        }
    
    # 5. 기본 응답 (매칭되는 키워드가 없는 경우)
    return {
        "type": "text",
        "content": f"입력해주신 \"'{user_message}'\"에 대해 정확히 이해하지 못했습니다.\n\n아래 내용 중 도움이 될 만한 항목을 선택해주세요:\n\n• 배송 정보\n• 반품/환불\n• 결제 방법\n• 멤버십\n• 상품 정보\n• 기타 문의는 문의게시판 이용"
    }

def get_quick_replies() -> list:
    """빠른 응답 버튼 목록"""
    return [
        {"label": "배송 정보", "action": "배송"},
        {"label": "반품/환불", "action": "반품"},
        {"label": "결제 방법", "action": "결제"},
        {"label": "멤버십", "action": "멤버십"},
        {"label": "사이즈 가이드", "action": "사이즈"},
        {"label": "고객센터", "action": "문의"}
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
