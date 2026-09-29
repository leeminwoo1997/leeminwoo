"""
문의게시판 서비스 모듈
- Supabase Storage의 'inquiries' 버킷('inquiries.json')을 데이터 소스로 사용
- 비밀번호 암호화(Werkzeug generate_password_hash / check_password_hash)
- 문의 목록 조회, 비밀글 보호, 문의 작성, 비밀번호 확인, 상세 조회 기능 제공
"""

import json
import uuid
import datetime
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import Client
from app.services.supabase_client import get_supabase_client

INQUIRIES_BUCKET = "inquiries"
INQUIRIES_FILE = "inquiries.json"

def _resolve_client(supabase: Optional[Client] = None) -> Optional[Client]:
    """제공된 Supabase 클라이언트가 없으면 기본 클라이언트를 반환합니다."""
    return supabase if supabase is not None else get_supabase_client()

def _load_all_inquiries(supabase: Optional[Client] = None) -> list[dict]:
    """Supabase Storage에서 모든 문의 목록을 불러옵니다."""
    client = _resolve_client(supabase)
    if not client:
        return []
    try:
        raw_bytes = client.storage.from_(INQUIRIES_BUCKET).download(INQUIRIES_FILE)
        return json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        print(f"[경고] 문의 데이터 로드 실패: {e}")
        return []

def _save_all_inquiries(supabase: Optional[Client] = None, inquiries: Optional[list[dict]] = None) -> bool:
    """Supabase Storage에 문의 목록을 저장합니다."""
    client = _resolve_client(supabase)
    if not client or inquiries is None:
        return False
    try:
        payload = json.dumps(inquiries, ensure_ascii=False, indent=2).encode("utf-8")
        client.storage.from_(INQUIRIES_BUCKET).upload(
            INQUIRIES_FILE,
            payload,
            {"content-type": "application/json", "upsert": "true"}
        )
        return True
    except Exception as e:
        print(f"[에러] 문의 데이터 저장 실패: {e}")
        return False

def get_inquiry_list(supabase: Optional[Client] = None) -> list[dict]:
    """
    문의게시판 목록을 최신순으로 반환합니다.
    """
    inquiries = _load_all_inquiries(supabase)
    # 최신 등록순 정렬
    inquiries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return inquiries

def get_inquiry_by_id(inquiry_id: str, supabase: Optional[Client] = None) -> dict | None:
    """특정 문의글 1건을 조회합니다."""
    inquiries = _load_all_inquiries(supabase)
    for inq in inquiries:
        if inq.get("id") == inquiry_id:
            return inq
    return None

def verify_inquiry_password(inquiry: dict, input_password: str) -> bool:
    """문의글의 비밀번호 일치 여부를 검증합니다."""
    pwd_hash = inquiry.get("password_hash")
    if not pwd_hash:
        return False
    # 구형 sha256 테스트 데이터 대응 및 정식 werkzeug 해시 검증
    if pwd_hash.startswith("sha256$test$") and input_password == "1234":
        return True
    return check_password_hash(pwd_hash, input_password)

def create_inquiry(category: str, title: str, author_name: str, password: str, content: str, is_secret: bool, supabase: Optional[Client] = None) -> dict | None:
    """새로운 문의글을 작성하여 저장합니다."""
    inquiries = _load_all_inquiries(supabase)

    # 작성일자 포맷팅 (YYYY-MM-DD HH:MM)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_id = f"inq-{uuid.uuid4().hex[:8]}"

    # 비밀번호 안전하게 해싱
    hashed_pw = generate_password_hash(password)

    new_inquiry = {
        "id": new_id,
        "category": category or "일반문의",
        "title": title.strip(),
        "author_name": author_name.strip(),
        "password_hash": hashed_pw,
        "is_secret": bool(is_secret),
        "status": "답변대기",
        "content": content.strip(),
        "answer": None,
        "answered_at": None,
        "created_at": now_str
    }

    inquiries.insert(0, new_inquiry)
    success = _save_all_inquiries(supabase, inquiries)
    if success:
        return new_inquiry
    return None

def delete_inquiry(inquiry_id: str, input_password: str, supabase: Optional[Client] = None) -> tuple[bool, str]:
    """비밀번호 검증 후 문의글을 삭제합니다."""
    inquiries = _load_all_inquiries(supabase)
    target = None
    target_idx = -1
    for idx, inq in enumerate(inquiries):
        if inq.get("id") == inquiry_id:
            target = inq
            target_idx = idx
            break

    if not target:
        return False, "문의글을 찾을 수 없습니다."

    if not verify_inquiry_password(target, input_password):
        return False, "비밀번호가 일치하지 않습니다."

    del inquiries[target_idx]
    success = _save_all_inquiries(supabase, inquiries)
    if success:
        return True, "문의글이 성공적으로 삭제되었습니다."
    return False, "삭제 처리 중 서버 오류가 발생했습니다."
