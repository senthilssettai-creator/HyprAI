class HyprAI {
    constructor() {
        this.apiBase = 'http://localhost:8765/api';
        this.chatMessages = document.getElementById('chat-messages');
        this.userInput = document.getElementById('user-input');
        this.sendBtn = document.getElementById('send-btn');
        this.screenshotCheckbox = document.getElementById('include-screenshot');
        
        this.init();
    }
    
    init() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                this.sendMessage();
            }
        });
        
        this.checkStatus();
        setInterval(() => this.updateSystemInfo(), 5000);
        
        this.addMessage('ai', 'HyprAI initialized! I have full control over your Hyprland system. What would you like me to do?');
    }
    
    async checkStatus() {
        try {
            const response = await fetch(`${this.apiBase}/status`);
            const data = await response.json();
            
            document.getElementById('status-text').textContent = 'Connected';
            document.querySelector('.status-dot').style.background = 'var(--success)';
            
            this.updateSystemInfo(data.system_state);
        } catch (error) {
            document.getElementById('status-text').textContent = 'Disconnected';
            document.querySelector('.status-dot').style.background = 'var(--error)';
        }
    }
    
    async sendMessage() {
        const query = this.userInput.value.trim();
        if (!query) return;
        
        const includeScreenshot = this.screenshotCheckbox.checked;
        
        this.addMessage('user', query);
        this.userInput.value = '';
        
        const thinkingMsg = this.addMessage('ai', '🤔 Analyzing and executing...');
        
        try {
            const response = await fetch(`${this.apiBase}/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, screenshot: includeScreenshot })
            });
            
            const data = await response.json();
            
            this.chatMessages.removeChild(thinkingMsg);
            
            if (data.success) {
                let responseText = data.response.explanation || 'Actions executed successfully';
                
                if (data.actions_executed && data.actions_executed.length > 0) {
                    responseText += '\n\n**Actions:**\n';
                    data.actions_executed.forEach((action, i) => {
                        if (action.success) {
                            responseText += `\n✓ Action ${i + 1}: ${JSON.stringify(action.result)}`;
                        } else {
                            responseText += `\n✗ Action ${i + 1}: ${action.error}`;
                        }
                    });
                }
                
                this.addMessage('ai', responseText);
            } else {
                this.addMessage('ai', `❌ Error: ${data.error}`);
            }
        } catch (error) {
            this.chatMessages.removeChild(thinkingMsg);
            this.addMessage('ai', `❌ Connection error: ${error.message}`);
        }
    }
    
    addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Basic markdown rendering
        content = content
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/`(.+?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
        
        contentDiv.innerHTML = content;
        messageDiv.appendChild(contentDiv);
        this.chatMessages.appendChild(messageDiv);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        
        return messageDiv;
    }
    
    updateSystemInfo(state) {
        if (!state) return;
        
        const activeWindow = state.active_window?.title || 'None';
        const workspace = state.active_window?.workspace?.id || '-';
        const windowCount = state.clients?.length || 0;
        
        document.getElementById('active-window').textContent = activeWindow;
        document.getElementById('workspace').textContent = workspace;
        document.getElementById('window-count').textContent = windowCount;
    }
}


function quickAction(query) {
    const app = window.hypraiApp;
    app.userInput.value = query;
    app.sendMessage();
}


// Initialize app
window.addEventListener('DOMContentLoaded', () => {
    window.hypraiApp = new HyprAI();
});