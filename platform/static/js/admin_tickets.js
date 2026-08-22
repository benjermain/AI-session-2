// ============================================================================
// VELLORA BIO PLATFORM - FAILURE TICKET RECOVERY CONTROLLER
// ============================================================================

const AdminTickets = {
    selectedTicketId: null,
    tickets: [],

    async init() {
        this.bindEvents();
        await this.fetchTickets();
    },

    bindEvents() {
        const btnRefresh = document.getElementById('btn-refresh-tickets');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => this.fetchTickets());
        }

        const btnResumeSubmit = document.getElementById('btn-ticket-resume-submit');
        if (btnResumeSubmit) {
            btnResumeSubmit.addEventListener('click', () => this.submitResume());
        }
    },

    async fetchTickets() {
        const tbody = document.getElementById('tickets-tbody');
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--cyan); padding:2rem;">Fetching failure tickets...</td></tr>';

        try {
            const res = await fetch('/api/admin/tickets');
            const data = await res.json();
            this.tickets = data.tickets || [];

            if (!this.tickets.length) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--emerald); padding:2rem;">✅ Zero active failure tickets. All workflows operating normally.</td></tr>';
                return;
            }

            tbody.innerHTML = this.tickets.map(t => {
                const isOpen = t.status === 'OPEN';
                return `
                    <tr>
                        <td><code style="color:var(--cyan); font-size:0.75rem;">${t.id.substring(0, 8)}...</code></td>
                        <td><strong style="color:var(--text-primary); font-size:0.8rem;">${t.workflow}</strong></td>
                        <td><code style="color:var(--amber); font-size:0.75rem;">${t.node || 'unknown_node'}</code></td>
                        <td style="color:var(--crimson); font-size:0.8rem; max-width:260px; word-break:break-word;">${t.error}</td>
                        <td>
                            <span class="agent-badge ${isOpen ? 'crimson' : 'emerald'}">${t.status}</span>
                        </td>
                        <td>
                            ${isOpen ? `
                                <button class="btn-secondary" style="color:var(--cyan); border-color:var(--cyan); font-size:0.75rem; padding:0.3rem 0.75rem;" onclick="AdminTickets.openResolveModal('${t.id}')">
                                    Inspect & Resume →
                                </button>
                            ` : `
                                <span style="font-size:0.75rem; color:var(--text-muted);">Resolved</span>
                            `}
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--crimson); padding:2rem;">Error fetching tickets: ${err.message}</td></tr>`;
        }
    },

    openResolveModal(ticketId) {
        const ticket = this.tickets.find(t => t.id === ticketId);
        if (!ticket) return;

        this.selectedTicketId = ticketId;
        const modal = document.getElementById('modal-ticket-resolve');
        const detailsEl = document.getElementById('ticket-modal-details');
        const editorEl = document.getElementById('ticket-modal-state-editor');

        detailsEl.innerHTML = `
            <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); border-radius:6px; padding:0.75rem; font-size:0.8rem;">
                <p><strong style="color:var(--crimson);">Error:</strong> ${ticket.error}</p>
                <p><strong>Failed Node:</strong> <code>${ticket.node}</code> • <strong>Workflow:</strong> <code>${ticket.workflow}</code></p>
            </div>
        `;

        editorEl.value = JSON.stringify(ticket.state, null, 2);
        modal.classList.add('active');
    },

    async submitResume() {
        if (!this.selectedTicketId) return;

        const modal = document.getElementById('modal-ticket-resolve');
        const editorEl = document.getElementById('ticket-modal-state-editor');

        let modifiedState = null;
        try {
            modifiedState = JSON.parse(editorEl.value);
        } catch (err) {
            App.showToast('Invalid JSON in state editor', 'error');
            return;
        }

        try {
            const res = await fetch('/api/admin/tickets/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticket_id: this.selectedTicketId,
                    action: 'resume',
                    modified_state: modifiedState
                })
            });

            const data = await res.json();
            if (res.ok) {
                App.showToast(`Ticket resolved! Workflow '${data.workflow}' resumed from checkpoint.`, 'success');
                modal.classList.remove('active');
                this.fetchTickets();
            } else {
                App.showToast(`Resume error: ${data.detail}`, 'error');
            }
        } catch (e) {
            App.showToast(`Network error: ${e.message}`, 'error');
        }
    }
};

window.AdminTickets = AdminTickets;
window.addEventListener('DOMContentLoaded', () => AdminTickets.init());
