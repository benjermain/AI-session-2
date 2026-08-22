// ============================================================================
// VELLORA BIO PLATFORM - USER MULTI-AGENT CHAT CONTROLLER
// ============================================================================

const Chat = {
    agents: [],
    currentAgentId: 'bioreactor_batch',
    currentThreadId: null,

    async init() {
        this.bindEvents();
        await this.fetchAgents();
    },

    bindEvents() {
        const btnSend = document.getElementById('btn-send-message');
        const inputPrompt = document.getElementById('chat-prompt-input');
        const btnClear = document.getElementById('btn-clear-chat');

        btnSend.addEventListener('click', () => this.sendMessage());
        inputPrompt.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });

        btnClear.addEventListener('click', () => {
            const container = document.getElementById('chat-messages-container');
            container.innerHTML = `
                <div class="message-card assistant">
                    <div class="message-bubble">
                        Thread cleared. Active Agent: <strong>${this.getCurrentAgent()?.name || this.currentAgentId}</strong>. Ready for new synthesis or evaluation instructions.
                    </div>
                </div>
            `;
            this.currentThreadId = null;
        });
    },

    async fetchAgents() {
        try {
            const res = await fetch('/api/agents');
            const data = await res.json();
            this.agents = data.agents || [];
            this.renderAgentCards();
            this.selectAgent(this.currentAgentId);
        } catch (e) {
            console.error('Failed to fetch agents', e);
        }
    },

    renderAgentCards() {
        const container = document.getElementById('agent-cards-container');
        container.innerHTML = this.agents.map(ag => `
            <div class="agent-card ${ag.id === this.currentAgentId ? 'active' : ''}" data-agent-id="${ag.id}">
                <div class="agent-card-header">
                    <span class="agent-name">${ag.name}</span>
                    <span class="agent-badge ${ag.color}">${ag.badge}</span>
                </div>
                <div class="agent-desc">${ag.description}</div>
                <div class="agent-tech-tags">
                    ${ag.techniques.map(t => `<span class="tech-tag">${t}</span>`).join('')}
                </div>
            </div>
        `).join('');

        container.querySelectorAll('.agent-card').forEach(card => {
            card.addEventListener('click', () => {
                const agId = card.getAttribute('data-agent-id');
                this.selectAgent(agId);
            });
        });
    },

    getCurrentAgent() {
        return this.agents.find(a => a.id === this.currentAgentId);
    },

    selectAgent(agentId) {
        this.currentAgentId = agentId;
        const ag = this.getCurrentAgent();
        if (!ag) return;

        // Highlight selected card
        document.querySelectorAll('.agent-card').forEach(c => {
            c.classList.toggle('active', c.getAttribute('data-agent-id') === agentId);
        });

        // Update chat header
        document.getElementById('current-agent-icon').textContent = ag.id.includes('bioreactor') ? '🧬' : (ag.id.includes('biosafety') ? '🛡️' : (ag.id.includes('redesign') ? '🧪' : (ag.id.includes('memory') ? '🧠' : '📐')));
        document.getElementById('current-agent-name').textContent = ag.name;
        document.getElementById('current-agent-techniques').textContent = ag.techniques.join(' • ');

        // Update default prompt suggestion
        const promptInput = document.getElementById('chat-prompt-input');
        if (ag.id === 'bioreactor_batch') {
            promptInput.placeholder = "e.g. Synthesize GFP marker batch with multi-phase incubation and sterility check...";
        } else if (ag.id === 'biosafety_escalation') {
            promptInput.placeholder = "e.g. Verify biosafety clearance and evaluate dual-use compliance for viral construct...";
        } else if (ag.id === 'vector_redesign') {
            promptInput.placeholder = "e.g. Run off-target alignment scan and redesign sequence if score exceeds threshold...";
        } else if (ag.id === 'memory_rag') {
            promptInput.placeholder = "e.g. What is Protocol 4.2b requirement for Risk Tier 3 payloads?";
        } else {
            promptInput.placeholder = "e.g. Decompose genetic synthesis validation workflow into DAG subtasks...";
        }
    },

    async sendMessage() {
        const inputPrompt = document.getElementById('chat-prompt-input');
        const text = inputPrompt.value.trim();
        if (!text) return;

        const researcherId = parseInt(document.getElementById('select-researcher').value, 10);
        const payloadId = parseInt(document.getElementById('select-payload').value, 10);
        const sequence = document.getElementById('input-sequence').value.trim() || 'ATCGATCGATCG';

        // Render user message
        this.appendMessage('user', text);
        inputPrompt.value = '';

        // Add loading placeholder
        const loadingId = 'loading-' + Date.now();
        this.appendLoading(loadingId);

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: this.currentAgentId,
                    message: text,
                    payload_id: payloadId,
                    researcher_id: researcherId,
                    sequence: sequence,
                    thread_id: this.currentThreadId,
                })
            });

            const data = await res.json();
            document.getElementById(loadingId)?.remove();

            if (data.thread_id) {
                this.currentThreadId = data.thread_id;
            }

            this.appendAssistantResult(data);
        } catch (err) {
            document.getElementById(loadingId)?.remove();
            this.appendMessage('assistant', `<span style="color:var(--crimson);">Error executing agent: ${err.message}</span>`);
        }
    },

    appendMessage(role, contentHtml) {
        const container = document.getElementById('chat-messages-container');
        const card = document.createElement('div');
        card.className = `message-card ${role}`;
        card.innerHTML = `<div class="message-bubble">${contentHtml}</div>`;
        container.appendChild(card);
        container.scrollTop = container.scrollHeight;
    },

    appendLoading(id) {
        const container = document.getElementById('chat-messages-container');
        const card = document.createElement('div');
        card.id = id;
        card.className = 'message-card assistant';
        card.innerHTML = `
            <div class="message-bubble" style="display:flex; align-items:center; gap:0.5rem; color:var(--cyan);">
                <span class="status-dot"></span>
                <span>Executing ${this.getCurrentAgent()?.name || 'Agent'}...</span>
            </div>
        `;
        container.appendChild(card);
        container.scrollTop = container.scrollHeight;
    },

    appendAssistantResult(data) {
        const container = document.getElementById('chat-messages-container');
        const card = document.createElement('div');
        card.className = 'message-card assistant';

        let stepsHtml = '';
        if (data.steps && data.steps.length) {
            stepsHtml = `
                <div class="execution-steps-card">
                    <div class="steps-title">
                        <span>⚡</span>
                        <span>State Execution Timeline</span>
                    </div>
                    <div class="steps-timeline">
                        ${data.steps.map(s => `
                            <div class="step-item ${s.status.toLowerCase()}">
                                <span class="step-icon">${s.status === 'COMPLETED' ? '✓' : (s.status === 'PAUSED' ? '⏸' : '✕')}</span>
                                <span>${s.name}</span>
                                <span style="font-size:0.7rem; color:var(--text-muted); margin-left:auto;">${s.status}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        let bannerHtml = '';
        if (data.status === 'PAUSED') {
            bannerHtml = `
                <div class="hitl-chat-banner" style="background:rgba(245,158,11,0.12); border:1px solid var(--amber); border-radius:8px; padding:0.75rem 1rem; margin-top:0.75rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                    <div>
                        <strong style="color:var(--amber);">⚠️ HITL Approval Required</strong>
                        <p style="font-size:0.75rem; color:var(--text-secondary); margin-top:0.2rem;">Task ID: <code>${data.task_id}</code></p>
                    </div>
                    <div style="display:flex; gap:0.5rem;">
                        <button class="btn-secondary" style="font-size:0.75rem; padding:0.35rem 0.75rem;" onclick="App.switchTab('tab-hitl')">
                            Inspect State →
                        </button>
                        <button class="btn-send" style="background:var(--emerald); color:#000; font-weight:700; font-size:0.75rem; padding:0.35rem 0.85rem;" onclick="Chat.quickApproveTask('${data.task_id}', this)">
                            Approve & Resume ✓
                        </button>
                    </div>
                </div>
            `;
        } else if (data.status === 'FAILED') {
            bannerHtml = `
                <div style="background:rgba(239,68,68,0.12); border:1px solid var(--crimson); border-radius:8px; padding:0.75rem 1rem; margin-top:0.75rem; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong style="color:var(--crimson);">🎫 Mid-Node Failure Caught</strong>
                        <p style="font-size:0.75rem; color:var(--text-secondary); margin-top:0.2rem;">Ticket ID: <code>${data.ticket_id}</code></p>
                    </div>
                    <button class="btn-secondary" style="background:var(--crimson); color:#fff; font-weight:700; font-size:0.75rem;" onclick="App.switchTab('tab-tickets')">
                        Inspect Ticket →
                    </button>
                </div>
            `;
        }

        let rawPayloadHtml = '';
        if (data.data) {
            rawPayloadHtml = `
                <div class="tool-call-details">
                    <div class="tool-call-header" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'">
                        <span>View Raw State Output</span>
                        <span>▼</span>
                    </div>
                    <pre class="tool-call-body" style="display:none;">${JSON.stringify(data.data, null, 2)}</pre>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="message-bubble">
                <p>${data.summary || data.status || 'Execution completed.'}</p>
                ${stepsHtml}
                ${bannerHtml}
                ${rawPayloadHtml}
            </div>
        `;

        container.appendChild(card);
        container.scrollTop = container.scrollHeight;
    },

    async quickApproveTask(taskId, btnEl) {
        if (!taskId) return;
        if (btnEl) {
            btnEl.disabled = true;
            btnEl.textContent = 'Resuming...';
        }

        try {
            const res = await fetch('/api/admin/hitl/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: taskId, approved: true })
            });

            const data = await res.json();
            if (res.ok) {
                App.showToast(`Task ${taskId} approved! Workflow resumed.`, 'success');
                if (btnEl) {
                    const banner = btnEl.closest('.hitl-chat-banner');
                    if (banner) {
                        banner.innerHTML = `<span style="color:var(--emerald); font-size:0.8rem; font-weight:600;">✓ Approved & Resumed (Task: ${taskId})</span>`;
                    }
                }
                if (data.resumed_result) {
                    this.appendAssistantResult({
                        summary: data.summary || `Workflow resumed and harvest completed.`,
                        steps: data.steps || [],
                        status: data.resumed_result.status || 'COMPLETED',
                        data: data.resumed_result,
                    });
                }
            } else {
                App.showToast(`Error: ${data.detail}`, 'error');
                if (btnEl) {
                    btnEl.disabled = false;
                    btnEl.textContent = 'Approve & Resume ✓';
                }
            }
        } catch (e) {
            App.showToast(`Network error: ${e.message}`, 'error');
            if (btnEl) {
                btnEl.disabled = false;
                btnEl.textContent = 'Approve & Resume ✓';
            }
        }
    }
};

window.Chat = Chat;
window.addEventListener('DOMContentLoaded', () => Chat.init());
