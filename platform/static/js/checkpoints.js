// ============================================================================
// VELLORA BIO PLATFORM - STATE CHECKPOINTS TIMELINE CONTROLLER
// ============================================================================

const Checkpoints = {
    init() {
        this.bindEvents();
    },

    bindEvents() {
        const btnFetch = document.getElementById('btn-fetch-checkpoints');
        const inputThread = document.getElementById('input-checkpoint-thread');

        if (btnFetch && inputThread) {
            btnFetch.addEventListener('click', () => this.fetchTimeline());
            inputThread.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') this.fetchTimeline();
            });
        }
    },

    async fetchTimeline() {
        const inputThread = document.getElementById('input-checkpoint-thread');
        const container = document.getElementById('checkpoint-timeline-container');
        const threadId = inputThread.value.trim();

        if (!threadId) {
            App.showToast('Please enter a Thread ID', 'warning');
            return;
        }

        container.innerHTML = '<p style="color:var(--cyan);">Fetching checkpoint history...</p>';

        try {
            const res = await fetch(`/api/checkpoints/${encodeURIComponent(threadId)}`);
            const data = await res.json();
            const history = data.history || [];

            if (!history.length) {
                container.innerHTML = `<p style="color:var(--amber);">No checkpoints found for Thread ID <code>${threadId}</code>.</p>`;
                return;
            }

            container.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:0.75rem; margin-top:0.5rem;">
                    <div style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:0.4rem;">
                        Found <strong>${history.length}</strong> persisted transitions for thread <code>${threadId}</code>:
                    </div>
                    ${history.map((cp, idx) => `
                        <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-subtle); border-radius:8px; padding:0.9rem 1rem;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.3rem;">
                                <div style="display:flex; align-items:center; gap:0.5rem;">
                                    <span class="step-icon" style="background:rgba(0,229,255,0.2); color:var(--cyan); font-size:0.7rem; width:20px; height:20px;">#${cp.step_index}</span>
                                    <strong style="color:var(--cyan); font-size:0.9rem;">Node: <code>${cp.node}</code></strong>
                                    <span style="font-size:0.75rem; color:var(--text-muted);">Workflow: ${cp.workflow}</span>
                                </div>
                                <span style="font-size:0.7rem; color:var(--text-muted);">${new Date(cp.created_at).toLocaleTimeString()}</span>
                            </div>
                            <div class="tool-call-details" style="margin-top:0.4rem;">
                                <div class="tool-call-header" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'">
                                    <span>Inspect Checkpoint State Snapshot</span>
                                    <span>▼</span>
                                </div>
                                <pre class="tool-call-body" style="display:none;">${JSON.stringify(cp.state, null, 2)}</pre>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } catch (err) {
            container.innerHTML = `<p style="color:var(--crimson);">Error: ${err.message}</p>`;
        }
    }
};

window.Checkpoints = Checkpoints;
window.addEventListener('DOMContentLoaded', () => Checkpoints.init());
