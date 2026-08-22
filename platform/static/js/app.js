// ============================================================================
// VELLORA BIO PLATFORM - MAIN APP CONTROLLER
// ============================================================================

const App = {
    currentTab: 'tab-chat',
    statsInterval: null,

    init() {
        this.setupNavigation();
        this.setupModals();
        this.setupMemoryDrawer();
        this.setupGeminiModal();
        this.fetchStats();
        this.checkGeminiStatus();
        this.statsInterval = setInterval(() => {
            this.fetchStats();
        }, 4000);
    },

    setupGeminiModal() {
        const btnOpen = document.getElementById('btn-open-gemini-modal');
        const modal = document.getElementById('modal-gemini-key');
        const btnSave = document.getElementById('btn-save-gemini-key');
        const inputKey = document.getElementById('input-gemini-api-key');

        if (btnOpen) {
            btnOpen.addEventListener('click', () => {
                modal.classList.add('active');
                this.checkGeminiStatus();
            });
        }

        if (btnSave) {
            btnSave.addEventListener('click', async () => {
                const key = inputKey.value.trim();
                if (!key) {
                    this.showToast('Please enter a valid Gemini API key', 'warning');
                    return;
                }
                try {
                    const res = await fetch('/api/config/llm', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ api_key: key, provider: 'gemini' })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        this.showToast('Gemini API Key activated and saved to .env!', 'success');
                        modal.classList.remove('active');
                        inputKey.value = '';
                        this.checkGeminiStatus();
                    } else {
                        this.showToast(`Error saving key: ${data.detail}`, 'error');
                    }
                } catch (e) {
                    this.showToast(`Network error: ${e.message}`, 'error');
                }
            });
        }
    },

    async checkGeminiStatus() {
        try {
            const res = await fetch('/api/config/llm');
            const data = await res.json();
            const icon = document.getElementById('gemini-status-icon');
            const text = document.getElementById('gemini-status-text');
            const statusEl = document.getElementById('gemini-current-status-text');

            if (data.configured) {
                if (icon) icon.textContent = '🟢';
                if (text) text.textContent = 'Gemini LLM Active';
                if (statusEl) statusEl.innerHTML = `<strong style="color:var(--emerald);">CONNECTED (${data.key_preview})</strong>`;
            } else {
                if (icon) icon.textContent = '⚡';
                if (text) text.textContent = 'Connect Gemini Key';
                if (statusEl) statusEl.innerHTML = '<span style="color:var(--amber);">Not configured (Using local simulation)</span>';
            }
        } catch (e) {
            // Ignore if offline
        }
    },

    setupNavigation() {
        const tabs = document.querySelectorAll('.nav-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTabId = tab.getAttribute('data-tab');
                this.switchTab(targetTabId);
            });
        });
    },

    switchTab(tabId) {
        // Update nav tabs
        document.querySelectorAll('.nav-tab').forEach(t => {
            t.classList.toggle('active', t.getAttribute('data-tab') === tabId);
        });

        // Update tab panels
        document.querySelectorAll('.tab-panel').forEach(p => {
            p.classList.toggle('active', p.id === tabId);
        });

        this.currentTab = tabId;

        // Trigger tab-specific refresh
        if (tabId === 'tab-tools' && window.AdminTools) window.AdminTools.fetchMatrix();
        if (tabId === 'tab-rag' && window.AdminRAG) window.AdminRAG.fetchDocuments();
        if (tabId === 'tab-hitl' && window.AdminHITL) window.AdminHITL.fetchTasks();
        if (tabId === 'tab-tickets' && window.AdminTickets) window.AdminTickets.fetchTickets();
    },

    setupModals() {
        document.querySelectorAll('.btn-close-modal').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modal = e.target.closest('.modal-overlay');
                if (modal) modal.classList.remove('active');
            });
        });

        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.classList.remove('active');
            });
        });
    },

    setupMemoryDrawer() {
        const btnToggle = document.getElementById('btn-toggle-memory');
        const drawer = document.getElementById('memory-drawer');
        const drawerBody = document.getElementById('memory-drawer-body');

        btnToggle.addEventListener('click', async () => {
            drawer.classList.add('active');
            drawerBody.innerHTML = '<p style="color:var(--cyan);">Loading live memory state...</p>';
            try {
                const res = await fetch('/api/memory/state');
                const data = await res.json();
                
                let factsHtml = data.active_facts.length 
                    ? data.active_facts.map(f => `<li><strong>${f.fact_key}</strong>: <code>${f.value}</code> (v${f.version})</li>`).join('')
                    : '<li>(No active semantic facts consolidated yet)</li>';

                let historyHtml = data.router_history.length
                    ? data.router_history.map(h => `<li>[${h.decision}] ${h.item_summary.substring(0, 50)}... <em>(${h.reasoning})</em></li>`).join('')
                    : '<li>(No overflow router decisions logged yet)</li>';

                drawerBody.innerHTML = `
                    <div style="display:flex; flex-direction:column; gap:1.25rem;">
                        <div class="data-table-card" style="padding:1rem;">
                            <h4 style="color:var(--cyan); margin-bottom:0.4rem; font-size:0.9rem;">1. Scratchpad (Working State)</h4>
                            <p><strong>Plan:</strong> ${data.scratchpad.current_plan || 'None'}</p>
                            <p><strong>Subgoal:</strong> ${data.scratchpad.active_subgoal || 'None'}</p>
                            <p><strong>Constraints:</strong> ${data.scratchpad.safety_constraints.join(', ') || 'None'}</p>
                        </div>
                        <div class="data-table-card" style="padding:1rem;">
                            <h4 style="color:var(--emerald); margin-bottom:0.4rem; font-size:0.9rem;">2. Active Semantic Facts (v1/v2 Versioned)</h4>
                            <ul style="padding-left:1.25rem; font-size:0.8rem; line-height:1.6;">${factsHtml}</ul>
                        </div>
                        <div class="data-table-card" style="padding:1rem;">
                            <h4 style="color:var(--purple); margin-bottom:0.4rem; font-size:0.9rem;">3. Promote-or-Drop Router Decisions</h4>
                            <ul style="padding-left:1.25rem; font-size:0.75rem; line-height:1.5;">${historyHtml}</ul>
                        </div>
                    </div>
                `;
            } catch (err) {
                drawerBody.innerHTML = `<p style="color:var(--crimson);">Error fetching memory: ${err.message}</p>`;
            }
        });
    },

    async fetchStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();

            const hitlBadge = document.getElementById('badge-hitl');
            if (data.pending_hitl_tasks > 0) {
                hitlBadge.textContent = data.pending_hitl_tasks;
                hitlBadge.style.display = 'inline-block';
            } else {
                hitlBadge.style.display = 'none';
            }

            const ticketBadge = document.getElementById('badge-tickets');
            if (data.open_failure_tickets > 0) {
                ticketBadge.textContent = data.open_failure_tickets;
                ticketBadge.style.display = 'inline-block';
            } else {
                ticketBadge.style.display = 'none';
            }
        } catch (e) {
            // Server offline or starting up
        }
    },

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = 'toast';
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'warning') icon = '⚠️';
        if (type === 'error') icon = '❌';

        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 250);
        }, 3500);
    }
};

window.addEventListener('DOMContentLoaded', () => App.init());
