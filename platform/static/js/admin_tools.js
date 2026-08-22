// ============================================================================
// VELLORA BIO PLATFORM - DYNAMIC MCP TOOL MATRIX CONTROLLER
// ============================================================================

const AdminTools = {
    async init() {
        this.bindEvents();
        await this.fetchMatrix();
    },

    bindEvents() {
        const btnRegister = document.getElementById('btn-register-tool-modal');
        if (btnRegister) {
            btnRegister.addEventListener('click', () => {
                const name = prompt('Enter new tool name (e.g. custom_primer_design):');
                if (!name) return;
                const desc = prompt('Enter tool description:');
                const handler = prompt('Enter handler import path (e.g. mcp_server.tools.defensive_synthesis:handle_submit_synthesis_job):', 'mcp_server.tools.defensive_synthesis:handle_submit_synthesis_job');
                
                if (name && handler) {
                    this.registerTool(name, desc || '', handler);
                }
            });
        }
    },

    async fetchMatrix() {
        const tbody = document.getElementById('tool-matrix-tbody');
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--cyan); padding:2rem;">Fetching live MCP tool registry...</td></tr>';
        
        try {
            const res = await fetch('/api/admin/tools');
            const data = await res.json();
            const tools = data.tools || [];
            const agents = data.agents || [];

            if (!tools.length) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:2rem;">No MCP tools currently registered.</td></tr>';
                return;
            }

            tbody.innerHTML = tools.map(tool => {
                const togglesHtml = agents.map(ag => {
                    const isChecked = tool.permissions[ag.id] ? 'checked' : '';
                    return `
                        <td style="text-align:center;">
                            <label class="toggle-switch">
                                <input type="checkbox" ${isChecked} onchange="AdminTools.togglePermission('${tool.name}', '${ag.id}', this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                        </td>
                    `;
                }).join('');

                return `
                    <tr>
                        <td>
                            <div style="font-family:'JetBrains Mono'; font-weight:600; color:var(--cyan);">${tool.name}</div>
                        </td>
                        <td style="font-size:0.8rem; color:var(--text-secondary); max-width:240px;">${tool.description}</td>
                        ${togglesHtml}
                    </tr>
                `;
            }).join('');
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--crimson); padding:2rem;">Error fetching MCP tools: ${err.message}</td></tr>`;
        }
    },

    async togglePermission(toolName, agentId, enabled) {
        try {
            const res = await fetch('/api/admin/tools/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: toolName,
                    agent_id: agentId,
                    enabled: enabled
                })
            });
            const data = await res.json();
            if (res.ok) {
                App.showToast(`Updated '${toolName}' for ${agentId} -> ${enabled ? 'ENABLED' : 'DISABLED'}`, 'success');
            } else {
                App.showToast(`Failed to update tool: ${data.detail || 'Error'}`, 'error');
                this.fetchMatrix();
            }
        } catch (e) {
            App.showToast(`Network error: ${e.message}`, 'error');
            this.fetchMatrix();
        }
    },

    async registerTool(name, desc, handlerPath) {
        try {
            const res = await fetch('/api/admin/tools/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    description: desc,
                    handler_path: handlerPath
                })
            });
            const data = await res.json();
            if (res.ok) {
                App.showToast(`Tool '${name}' registered successfully!`, 'success');
                this.fetchMatrix();
            } else {
                App.showToast(`Registration failed: ${data.detail}`, 'error');
            }
        } catch (e) {
            App.showToast(`Error: ${e.message}`, 'error');
        }
    }
};

window.AdminTools = AdminTools;
window.addEventListener('DOMContentLoaded', () => AdminTools.init());
