// ============================================================================
// VELLORA BIO PLATFORM - DYNAMIC RAG KNOWLEDGE BASE CONTROLLER
// ============================================================================

const AdminRAG = {
    async init() {
        this.bindEvents();
        await this.fetchDocuments();
    },

    bindEvents() {
        const btnAdd = document.getElementById('btn-add-rag-modal');
        if (btnAdd) {
            btnAdd.addEventListener('click', () => {
                const text = prompt('Enter new clinical biosafety protocol or policy text:');
                if (text && text.trim()) {
                    this.addDocument(text.trim());
                }
            });
        }

        const btnSearch = document.getElementById('btn-rag-test-search');
        const inputSearch = document.getElementById('input-rag-test-query');
        if (btnSearch && inputSearch) {
            btnSearch.addEventListener('click', () => this.testSearch());
            inputSearch.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') this.testSearch();
            });
        }
    },

    async fetchDocuments() {
        const tbody = document.getElementById('rag-docs-tbody');
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--cyan); padding:2rem;">Fetching RAG knowledge base...</td></tr>';

        try {
            const res = await fetch('/api/admin/rag');
            const data = await res.json();
            const docs = data.documents || [];

            if (!docs.length) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:2rem;">No documents in knowledge base.</td></tr>';
                return;
            }

            tbody.innerHTML = docs.map(doc => `
                <tr>
                    <td><code style="color:var(--cyan);">#${doc.id}</code></td>
                    <td style="font-size:0.85rem; line-height:1.4;">${doc.text}</td>
                    <td><span class="brand-tag">${doc.source}</span></td>
                    <td>
                        <button class="btn-secondary" style="color:var(--crimson); border-color:rgba(239,68,68,0.3); font-size:0.75rem; padding:0.25rem 0.6rem;" onclick="AdminRAG.deleteDocument('${doc.id}')">
                            Delete
                        </button>
                    </td>
                </tr>
            `).join('');
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--crimson); padding:2rem;">Error fetching documents: ${err.message}</td></tr>`;
        }
    },

    async addDocument(text) {
        try {
            const res = await fetch('/api/admin/rag', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, source: 'admin_upload' })
            });
            const data = await res.json();
            if (res.ok) {
                App.showToast(`Document #${data.doc_id} ingested into Vector + BM25 stores!`, 'success');
                this.fetchDocuments();
            } else {
                App.showToast(`Failed to add document: ${data.detail}`, 'error');
            }
        } catch (e) {
            App.showToast(`Error: ${e.message}`, 'error');
        }
    },

    async deleteDocument(docId) {
        if (!confirm(`Are you sure you want to remove Document #${docId} from live RAG retrieval?`)) return;

        try {
            const res = await fetch(`/api/admin/rag/${docId}`, { method: 'DELETE' });
            const data = await res.json();
            if (res.ok) {
                App.showToast(`Document #${docId} deleted and indexes synchronized.`, 'success');
                this.fetchDocuments();
            } else {
                App.showToast(`Failed to delete: ${data.detail}`, 'error');
            }
        } catch (e) {
            App.showToast(`Error: ${e.message}`, 'error');
        }
    },

    async testSearch() {
        const inputSearch = document.getElementById('input-rag-test-query');
        const resultsContainer = document.getElementById('rag-test-results');
        const query = inputSearch.value.trim();
        if (!query) return;

        resultsContainer.innerHTML = '<span style="color:var(--text-muted);">Querying Hybrid (Cosine ANN + BM25)...</span>';

        try {
            const res = await fetch('/api/admin/rag/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query, top_k: 2 })
            });
            const data = await res.json();
            if (data.results && data.results.length) {
                resultsContainer.innerHTML = `
                    <div style="background:rgba(0,0,0,0.5); padding:0.75rem; border-radius:6px; margin-top:0.5rem;">
                        <strong style="color:var(--cyan); font-size:0.8rem;">Top Retrieved Context (${data.results.length} matches):</strong>
                        <ol style="margin-top:0.4rem; padding-left:1.25rem; font-size:0.8rem; line-height:1.5;">
                            ${data.results.map(r => `<li>${r}</li>`).join('')}
                        </ol>
                    </div>
                `;
            } else {
                resultsContainer.innerHTML = '<span style="color:var(--amber);">No relevant policy matches found for this query.</span>';
            }
        } catch (e) {
            resultsContainer.innerHTML = `<span style="color:var(--crimson);">Search error: ${e.message}</span>`;
        }
    }
};

window.AdminRAG = AdminRAG;
window.addEventListener('DOMContentLoaded', () => AdminRAG.init());
