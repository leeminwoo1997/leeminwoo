/**
 * 플로팅 챗봇 위젯 - JavaScript
 * 실시간 채팅 기능 구현
 */

// 초기화 함수
document.addEventListener('DOMContentLoaded', function() {
    loadChatHistory();
    loadQuickReplies();
    initChatbotWidget();
});

// ===========================
// 1. 챗봇 위젯 토글 기능
// ===========================
function toggleChatbot() {
    const widget = document.getElementById('chatbot-widget');
    widget.classList.toggle('collapsed');
    
    // 위젯이 열릴 때 메시지 스크롤 하단으로
    if (!widget.classList.contains('collapsed')) {
        setTimeout(() => {
            scrollChatToBottom();
        }, 100);
    }
}

function initChatbotWidget() {
    // 초기 상태: 열려있음
    const widget = document.getElementById('chatbot-widget');
    if (widget.classList.contains('collapsed')) {
        widget.classList.remove('collapsed');
    }
}

// ===========================
// 2. 채팅 히스토리 로드
// ===========================
async function loadChatHistory() {
    try {
        const response = await fetch('/chat/api/messages', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) return;
        
        const data = await response.json();
        const messagesContainer = document.getElementById('chatbot-messages');
        
        // 기존 메시지 제거 (초기 환영 메시지 제외)
        const existingMessages = messagesContainer.querySelectorAll('.chatbot-message:not(:first-child)');
        existingMessages.forEach(msg => msg.remove());
        
        // 채팅 히스토리 로드
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                appendMessage(msg.sender_type, msg.content);
            });
        }
    } catch (error) {
        console.error('채팅 히스토리 로드 실패:', error);
    }
}

// ===========================
// 3. 메시지 전송 함수
// ===========================
async function sendChatbotMessage() {
    const inputField = document.getElementById('chatbot-input-field');
    const message = inputField.value.trim();
    
    if (!message) {
        alert('메시지를 입력해주세요.');
        return;
    }
    
    // 사용자 메시지 표시
    appendMessage('user', message);
    inputField.value = '';
    
    // 로딩 표시
    const loadingMsg = appendLoadingMessage();
    
    try {
        const response = await fetch('/chat/api/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: message })
        });
        
        if (!response.ok) {
            throw new Error('메시지 전송 실패');
        }
        
        const data = await response.json();
        
        // 로딩 메시지 제거
        if (loadingMsg) {
            loadingMsg.remove();
        }
        
        // 챗봇 응답 표시
        if (data.bot_response) {
            appendMessage('bot', data.bot_response.content);
        }
        
        // 스크롤 하단으로
        scrollChatToBottom();
        
    } catch (error) {
        console.error('메시지 전송 실패:', error);
        if (loadingMsg) {
            loadingMsg.remove();
        }
        appendMessage('bot', '죄송합니다. 잠시 후 다시 시도해주세요.');
    }
    
    // 입력 필드 포커스
    inputField.focus();
}

function handleChatbotKeypress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatbotMessage();
    }
}

// ===========================
// 4. 메시지 추가 함수
// ===========================
function appendMessage(senderType, content) {
    const messagesContainer = document.getElementById('chatbot-messages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chatbot-message ${senderType}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    scrollChatToBottom();
    return messageDiv;
}

function appendLoadingMessage() {
    const messagesContainer = document.getElementById('chatbot-messages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chatbot-message bot-message loading';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'dot';
        contentDiv.appendChild(dot);
    }
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    scrollChatToBottom();
    return messageDiv;
}

function scrollChatToBottom() {
    const messagesContainer = document.getElementById('chatbot-messages');
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// ===========================
// 5. 빠른 응답 버튼 로드
// ===========================
async function loadQuickReplies() {
    try {
        const response = await fetch('/chat/api/quick-replies', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) return;
        
        const data = await response.json();
        const repliesContainer = document.getElementById('chatbot-quick-replies');
        
        if (data.replies && data.replies.length > 0) {
            data.replies.forEach(reply => {
                const btn = document.createElement('button');
                btn.className = 'quick-reply-btn';
                btn.textContent = reply.label;
                btn.onclick = () => {
                    document.getElementById('chatbot-input-field').value = reply.action;
                    sendChatbotMessage();
                };
                repliesContainer.appendChild(btn);
            });
        }
    } catch (error) {
        console.error('빠른 응답 버튼 로드 실패:', error);
    }
}

// ===========================
// 6. 사용자 정보 업데이트
// ===========================
function updateChatbotUser(userId) {
    // 필요시 사용자 정보를 기반으로 챗봇 동작 커스터마이징
    // 예: 이전 대화 내역 로드, 사용자 맞춤 응답 등
    loadChatHistory();
}
