// ============================================================================
// VELLORA BIO PLATFORM - HITL ESCALATION CONTROLLER
// ============================================================================

const AdminHITL = {
    selectedTaskId: null,
    tasks: [],

    async init() {
        this.bindEvents();
        await this.fetchTasks();
    },

    bindEvents() {
        const btnRefresh = document.getElementById('btn-refresh-hitl');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => this.fetchTasks());
        }

        const btnApprove = document.getElementById('btn-hitl-approve');
        const btnReject = document.getElementById('btn-hitl-reject');

        if (btnApprove) {
            btnApprove.addEventListener('click', () => this.resolveCurrentTask(true));
        }
        if (btnReject) {
            btnReject.addEventListener('click', () => this.resolveCurrentTask(false));
        }
    },

    async fetchTasks() {
        const container = document.getElementById('hitl-tasks-container');
        container.innerHTML = '<p style="color:var(--cyan); text-align:center; padding:2rem;">Fetching HITL task queue...</p>';

        try {
            const res = await fetch('/api/admin/hitl');
            const data = await res.json();
            this.tasks = data.tasks || [];

            if (!this.tasks.length) {
                container.innerHTML = `
                    <div class="data-table-card" style="padding:2.5rem; text-align:center;">
                        <span style="font-size:2rem;">✅</span>
                        <h3 style="margin-top:0.75rem; color:var(--emerald);">All Queues Clear</h3>
                        <p style="color:var(--text-secondary); font-size:0.85rem; margin-top:0.25rem;">No state graphs are currently paused for human approval.</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = this.tasks.map(task => {
                const isPending = task.status === 'PENDING';
                const statusColor = isPending ? 'var(--amber)' : (task.status === 'APPROVED' ? 'var(--emerald)' : 'var(--crimson)');
                
                return `
                    <div class="data-table-card" style="padding:1.25rem; border-left: 4px solid ${statusColor};">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div>
                                <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.4rem;">
                                    <span class="agent-badge ${isPending ? 'amber' : (task.status === 'APPROVED' ? 'emerald' : 'crimson')}">${task.status}</span>
                                    <strong style="font-size:1rem; color:var(--text-primary);">Workflow: <code>${task.workflow}</code></strong>
                                    <span style="font-size:0.75rem; color:var(--text-muted);">Task: <code>${task.id}</code></span>
                                </div>
                                <p style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:0.5rem;">
                                    <strong>Requested By:</strong> ${task.requested_by || 'System Escalation'} • 
                                    <strong>Created:</strong> ${new Date(task.created_at).toLocaleString()}
                                </p>
                                <div style="font-size:0.8rem; color:var(--text-muted);">
                                    Reason / Context: ${task.state.hitl_reason || task.state.request || 'High-risk policy threshold reached.'}
                                </div>
                            </div>
                            <div style="display:flex; gap:0.5rem;">
                                ${isPending ? `
                                    <button class="btn-send" style="background:var(--amber); color:#000; font-size:0.8rem; padding:0.5rem 1rem;" onclick="AdminHITL.openDecisionModal('${task.id}')">
                                        Review & Decide →
                                    </button>
                                ` : `
                                    <span style="font-size:0.8rem; color:${statusColor}; font-weight:600;">Resolved as ${task.status}</span>
                                `}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (err) {
            container.innerHTML = `<p style="color:var(--crimson); text-align:center; padding:2rem;">Error fetching HITL tasks: ${err.message}</p>`;
        }
    },

    openDecisionModal(taskId) {
        const task = this.tasks.find(t => t.id === taskId);
        if (!task) return;

        this.selectedTaskId = taskId;
        const modal = document.getElementById('modal-hitl-decision');
        const detailsEl = document.getElementById('hitl-modal-details');
        const stateEl = document.getElementById('hitl-modal-state');

        detailsEl.innerHTML = `
            <p><strong>Workflow:</strong> ${task.workflow}</p>
            <p><strong>Task ID:</strong> <code>${task.id}</code></p>
            <p><strong>Escalation Reason:</strong> ${task.state.hitl_reason || task.state.request || 'High risk gate reached.'}</p>
        `;

        stateEl.textContent = JSON.stringify(task.state, null, 2);
        modal.classList.add('active');
    },

    async resolveCurrentTask(approved) {
        if (!this.selectedTaskId) return;

        const modal = document.getElementById('modal-hitl-decision');
        try {
            const res = await fetch('/api/admin/hitl/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: this.selectedTaskId,
                    approved: approved
                })
            });

            const data = await res.json();
            if (res.ok) {
                App.showToast(`Task ${this.selectedTaskId} resolved as ${data.decision}! Workflow resumed.`, 'success');
                modal.classList.remove('active');
                this.fetchTasks();

                // Append the resumed completion result into Chat window
                if (window.Chat && data.resumed_result) {
                    Chat.appendAssistantResult({
                        summary: data.summary || `Workflow resumed after ${data.decision.toLowerCase()} sign-off.`,
                        steps: data.steps || [],
                        status: data.resumed_result.status || 'COMPLETED',
                        data: data.resumed_result,
                    });
                }

                // Switch back to Chat tab so the user sees the live harvest/result
                App.switchTab('tab-chat');
            } else {
                App.showToast(`Resolution error: ${data.detail}`, 'error');
            }
        } catch (e) {
            App.showToast(`Network error: ${e.message}`, 'error');
        }
    }
};

window.AdminHITL = AdminHITL;
window.addEventListener('DOMContentLoaded', () => AdminHITL.init());
