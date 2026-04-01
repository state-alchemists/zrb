let currentSessionId = null;
let eventSource = null;
let pendingApproval = null;
let currentPage = 1;
let totalPages = 1;
let isInEditMode = false;
let streamingBubble = null;
let thinkingBubble = null;

async function loadSessions(page = 1) {
    currentPage = page;
    const response = await fetch(`/api/v1/chat/sessions?page=${page}&limit=10`);
    const data = await response.json();
    const sessionList = document.getElementById('session-list');
    totalPages = data.total_pages || 1;
    
    if (data.sessions.length === 0 && page === 1) {
        sessionList.innerHTML = '<p>No sessions yet. Create one to start chatting!</p>';
    } else {
        sessionList.innerHTML = data.sessions.map(session => `
            <div class="session-item" data-session-id="${session.session_id}" data-session-name="${session.session_name}">
                <span class="session-name">${session.session_name}</span>
                <span class="session-info">
                    ${session.is_processing ? '⏳ ' : ''}
                    ${session.message_count} messages
                </span>
            </div>
        `).join('');
    }
    
    sessionList.querySelectorAll('.session-item').forEach(item => {
        item.addEventListener('click', () => {
            selectSession(item.dataset.sessionId, item.dataset.sessionName);
        });
    });
    
    renderPagination(data.page, totalPages);
}

function renderPagination(page, total) {
    const pagination = document.getElementById('pagination');
    if (!pagination) return;
    
    let html = '';
    if (total > 1) {
        const maxVisible = 5;
        let start = Math.max(1, page - Math.floor(maxVisible / 2));
        let end = Math.min(total, start + maxVisible - 1);
        
        if (end - start < maxVisible - 1) {
            start = Math.max(1, end - maxVisible + 1);
        }
        
        html += `<button class="pagination-btn first-btn" ${page <= 1 ? 'disabled' : ''}>⏮ First</button>`;
        html += `<button class="pagination-btn prev-btn" ${page <= 1 ? 'disabled' : ''}>◀ Prev</button>`;
        
        for (let i = start; i <= end; i++) {
            html += `<button class="pagination-btn page-btn" data-page="${i}" ${i === page ? 'disabled' : ''}>${i}</button>`;
        }
        
        html += `<button class="pagination-btn next-btn" ${page >= total ? 'disabled' : ''}>Next ▶</button>`;
        html += `<button class="pagination-btn last-btn" ${page >= total ? 'disabled' : ''}>Last ⏭</button>`;
    }
    pagination.innerHTML = html;
    
    pagination.querySelectorAll('.pagination-btn:not([disabled])').forEach(btn => {
        btn.addEventListener('click', () => {
            const p = btn.dataset.page;
            if (p) {
                loadSessions(parseInt(p));
            } else {
                if (btn.classList.contains('first-btn') && page > 1) loadSessions(1);
                if (btn.classList.contains('prev-btn') && page > 1) loadSessions(page - 1);
                if (btn.classList.contains('next-btn') && page < total) loadSessions(page + 1);
                if (btn.classList.contains('last-btn') && page < total) loadSessions(total);
            }
        });
    });
}

async function selectSession(sessionId, sessionName) {
    currentSessionId = sessionId;
    document.getElementById('session-selector').classList.add('hidden');
    document.getElementById('chat-container').classList.remove('hidden');
    document.getElementById('current-session-name').textContent = sessionName || sessionId;

    await loadMessages();
    connectSSE();
    pollApproval();
}

function backToSessions() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    currentSessionId = null;
    document.getElementById('chat-container').classList.add('hidden');
    document.getElementById('session-selector').classList.remove('hidden');
    loadSessions();
}

async function createNewSession() {
    const nameInput = document.getElementById('new-session-name');
    const sessionName = nameInput.value.trim();
    nameInput.value = '';
    const response = await fetch('/api/v1/chat/sessions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_name: sessionName || undefined})
    });
    const data = await response.json();
    selectSession(data.session_id, data.session_name);
}

async function deleteSession() {
    if (!currentSessionId) return;
    if (!confirm('Delete this session?')) return;
    
    await fetch(`/api/v1/chat/sessions/${currentSessionId}`, {
        method: 'DELETE'
    });
    backToSessions();
}

async function loadMessages() {
    if (!currentSessionId) return;
    
    const response = await fetch(`/api/v1/chat/sessions/${currentSessionId}/messages`);
    const data = await response.json();
    
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = data.messages.map(msg => {
        const role = msg.role === 'user' ? 'user' : 'assistant';
        const content = escapeHtml(msg.content || '');
        return `<div class="message ${role}"><div class="message-content">${content}</div></div>`;
    }).join('');
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

function connectSSE() {
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource(`/api/v1/chat/sessions/${currentSessionId}/streaming`);
    
    eventSource.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        console.log('SSE message:', data);
        
        if (data.status === 'connected') {
            console.log('SSE connected');
            return;
        }
        
        if (data.text) {
            const messagesDiv = document.getElementById('messages');
            const kind = data.type || 'text';

            if (kind === 'streaming') {
                // Remove ephemeral progress spinner
                const spinner = document.getElementById('sse-progress');
                if (spinner) spinner.remove();
                // Append to streaming bubble, creating it if needed
                if (!streamingBubble || !messagesDiv.contains(streamingBubble)) {
                    streamingBubble = document.createElement('div');
                    streamingBubble.className = 'message assistant streaming';
                    const content = document.createElement('div');
                    content.className = 'message-content';
                    streamingBubble.appendChild(content);
                    messagesDiv.appendChild(streamingBubble);
                }
                streamingBubble.querySelector('.message-content').appendChild(
                    document.createTextNode(data.text)
                );

            } else if (kind === 'thinking') {
                // Remove ephemeral progress spinner
                const spinner = document.getElementById('sse-progress');
                if (spinner) spinner.remove();
                // Append to thinking bubble, creating it if needed
                if (!thinkingBubble || !messagesDiv.contains(thinkingBubble)) {
                    thinkingBubble = document.createElement('div');
                    thinkingBubble.className = 'message assistant thinking';
                    const content = document.createElement('div');
                    content.className = 'message-content';
                    thinkingBubble.appendChild(content);
                    messagesDiv.appendChild(thinkingBubble);
                }
                thinkingBubble.querySelector('.message-content').appendChild(
                    document.createTextNode(data.text)
                );

            } else if (kind === 'tool_call') {
                // Persistent tool call row (not ephemeral)
                const row = document.createElement('div');
                row.className = 'message tool-call';
                const content = document.createElement('div');
                content.className = 'message-content';
                content.textContent = data.text;
                row.appendChild(content);
                messagesDiv.appendChild(row);

            } else if (kind === 'usage') {
                // Usage stats footer row
                const row = document.createElement('div');
                row.className = 'message usage';
                const content = document.createElement('div');
                content.className = 'message-content';
                content.textContent = data.text;
                row.appendChild(content);
                messagesDiv.appendChild(row);

            } else if (kind === 'progress') {
                // Ephemeral spinner — replaced in place
                let spinner = document.getElementById('sse-progress');
                if (!spinner) {
                    spinner = document.createElement('div');
                    spinner.id = 'sse-progress';
                    spinner.className = 'message activity';
                    messagesDiv.appendChild(spinner);
                }
                spinner.textContent = data.text;

            } else {
                // kind === 'text' or unknown: normal assistant message
                const spinner = document.getElementById('sse-progress');
                if (spinner) spinner.remove();
                const lastMsg = messagesDiv.lastElementChild;
                if (lastMsg && lastMsg.classList.contains('assistant') &&
                    !lastMsg.classList.contains('tool-call') &&
                    !lastMsg.classList.contains('usage')) {
                    lastMsg.querySelector('.message-content').appendChild(
                        document.createTextNode(data.text)
                    );
                } else {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = 'message assistant';
                    const msgContent = document.createElement('div');
                    msgContent.className = 'message-content';
                    msgContent.appendChild(document.createTextNode(data.text));
                    msgDiv.appendChild(msgContent);
                    messagesDiv.appendChild(msgDiv);
                }
            }

            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        // Don't call checkApproval() here - polling handles it
    };
    
    eventSource.onerror = (error) => {
        console.log('SSE error, reconnecting...', error);
        setTimeout(connectSSE, 3000);
    };
}

async function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    
    if (!message || !currentSessionId) {
        console.log('sendMessage: empty message or no session');
        return;
    }
    
    input.value = '';

    // Reset streaming state for new response
    streamingBubble = null;
    thinkingBubble = null;

    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML += `<div class="message user"><div class="message-content">${escapeHtml(message)}</div></div>`;
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    try {
        const response = await fetch(`/api/v1/chat/sessions/${currentSessionId}/messages`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });
        console.log('sendMessage response:', response.status, await response.json());
    } catch (e) {
        console.error('sendMessage error:', e);
    }
}

async function checkApproval() {
    if (!currentSessionId) return;
    
    const response = await fetch(`/api/v1/chat/sessions/${currentSessionId}/approval`);
    const data = await response.json();
    
    console.log('checkApproval response:', JSON.stringify(data));
    
    if (data.pending_approvals.length > 0 || data.is_waiting_for_edit) {
        pendingApproval = data;
        showApprovalPanel(data);
    } else {
        pendingApproval = null;
        hideApprovalPanel();
    }
}

function showApprovalPanel(data) {
    const panel = document.getElementById('approval-panel');
    const content = document.getElementById('approval-content');
    const editPanel = document.getElementById('edit-panel');
    const editArgsInput = document.getElementById('edit-args');
    
    console.log('showApprovalPanel called:', {
        is_waiting_for_edit: data.is_waiting_for_edit,
        editing_args: data.editing_args,
        pending_count: data.pending_approvals.length
    });
    
    if (data.is_waiting_for_edit) {
        content.innerHTML = '<p>Edit the tool arguments and submit:</p>';
        editPanel.classList.remove('hidden');
        // Only populate textarea on first entry into edit mode to avoid overwriting user edits
        if (!isInEditMode && data.editing_args) {
            const jsonStr = JSON.stringify(data.editing_args, null, 2);
            editArgsInput.value = jsonStr;
            isInEditMode = true;
        }
    } else if (data.pending_approvals.length > 0) {
        const approval = data.pending_approvals[0];
        content.innerHTML = `
            <p><strong>Tool:</strong> ${approval.tool_name}</p>
            <p><strong>Args:</strong></p>
            <pre>${JSON.stringify(approval.tool_args, null, 2)}</pre>
        `;
        editPanel.classList.add('hidden');
        editArgsInput.value = '';
    }
    
    panel.classList.remove('hidden');
}

function hideApprovalPanel() {
    document.getElementById('approval-panel').classList.add('hidden');
    document.getElementById('edit-panel').classList.add('hidden');
    document.getElementById('edit-args').value = '';
    pendingApproval = null;
    isInEditMode = false;
}

async function handleApproval(action) {
    if (!currentSessionId) return;
    
    let message;
    let isApprovalAction = false;
    
    if (action === 'edit') {
        const args = document.getElementById('edit-args').value;
        if (args.trim()) {
            try {
                const parsed = JSON.parse(args);
                message = parsed;
                isApprovalAction = true;
            } catch (e) {
                message = args;
                isApprovalAction = true;
            }
        } else {
            message = "edit";
            isApprovalAction = true;
        }
    } else {
        // y, n, or other approval actions
        message = action;
        isApprovalAction = true;
    }
    
    await fetch(`/api/v1/chat/sessions/${currentSessionId}/messages`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            message,
            isApprovalAction: isApprovalAction
        })
    });
    
    hideApprovalPanel();
}

function pollApproval() {
    setInterval(async () => {
        if (currentSessionId) {
            await checkApproval();
        }
    }, 2000);
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('new-session-btn').addEventListener('click', createNewSession);
    document.getElementById('back-to-sessions').addEventListener('click', backToSessions);
    document.getElementById('delete-session-btn').addEventListener('click', deleteSession);
    document.getElementById('send-btn').addEventListener('click', sendMessage);
    document.getElementById('approve-btn').addEventListener('click', () => handleApproval('y'));
    document.getElementById('deny-btn').addEventListener('click', () => handleApproval('n'));
    document.getElementById('edit-btn').addEventListener('click', () => handleApproval('edit'));
    document.getElementById('submit-edit-btn').addEventListener('click', () => handleApproval('edit'));
    
    const input = document.getElementById('message-input');
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    loadSessions();
});
