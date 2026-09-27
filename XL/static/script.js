// ========== 方块君 - Minecraft AI 前端 ==========

// DOM
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const messagesContainer = document.getElementById('messagesContainer');
const sendBtn = document.getElementById('sendBtn');
const clearChatBtn = document.getElementById('clearChatBtn');

const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const uploadProgress = document.getElementById('uploadProgress');
const fileListEl = document.getElementById('fileList');
const docCountEl = document.getElementById('docCount');
const chunkCountEl = document.getElementById('chunkCount');
const clearKbBtn = document.getElementById('clearKbBtn');
const refreshKbBtn = document.getElementById('refreshKbBtn');
const useRagToggle = document.getElementById('useRagToggle');
const systemStatusEl = document.getElementById('systemStatus');
const categoryGrid = document.getElementById('categoryGrid');

let sessionId = 'mc_' + Date.now();

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    autoResize();
    setupUpload();
    checkStatus();
    loadCategories();
    loadKbStats();
    
    clearChatBtn.onclick = clearChat;
    clearKbBtn.onclick = clearKB;
    refreshKbBtn.onclick = loadKbStats;
});

function autoResize() {
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        sendBtn.disabled = !this.value.trim();
    });
}

// ========== 系统状态 ==========
async function checkStatus() {
    try {
        const r = await fetch('/api/status');
        const d = await r.json();
        const ai = d.ai_engine;
        const kb = d.knowledge_base;
        
        if (ai.connected) {
            let html = `<span class="status-online">&#10003; 自建AI引擎运行中</span>`;
            html += ` <span class="model-tag">${ai.model || 'Hybrid-A+B'}</span>`;
            
            // 显示引擎统计
            if (ai.stats) {
                html += ` <span class="engine-stats" style="font-size:10px;color:var(--accent)">
                    [规则:${ai.stats.mc_engine || 0} | 聊天:${ai.stats.chat_brain || 0}]
                </span>`;
            }
            systemStatusEl.innerHTML = html;
        } else {
            systemStatusEl.innerHTML = `
                <span class="status-offline">&#10007; AI引擎未就绪</span>
                <div style="font-size:10px;color:var(--text-muted);margin-top:4px">
                    ${ai.error || '请检查服务是否正常运行'}
                </div>`;
        }
        
        chunkCountEl.textContent = kb.total_documents || 0;
        if (kb.sources && Object.keys(kb.sources).length > 0) {
            renderFileList(kb.sources);
            docCountEl.textContent = Object.keys(kb.sources).length;
        }
    } catch(e) {
        systemStatusEl.innerHTML = '<span class="status-offline">&#10007; 服务未启动</span>';
    }
}

// ========== MC分类快捷入口 ==========
async function loadCategories() {
    try {
        const r = await fetch('/api/mc/categories');
        const d = await r.json();
        if (d.success && d.categories) {
            const cats = Object.entries(d.categories);
            categoryGrid.innerHTML = cats.map(([key, cat]) => `
                <button class="cat-btn" onclick="askCategory('${key}')">
                    <span class="cat-icon">${cat.icon}</span>
                    <span>${cat.name}</span>
                </button>
            `).join('');
        }
    } catch(e) { 
        categoryGrid.innerHTML = '<span class="cat-placeholder">加载失败</span>'; 
    }
}

function askCategory(catKey) {
    const prompts = {
        crafting: "请详细介绍Minecraft基础合成配方，包括工具、方块和常用物品",
        mobs: "请介绍Minecraft中的主要怪物和Boss生物，包括它们的属性、掉落物和应对方法",
        commands: "列出Minecraft最常用的游戏指令，包括生成物品、设置游戏模式等",
        redstone: "讲解Minecraft红石工程基础知识，包括红石元件、基本电路和常见自动化装置",
        enchanting: "详细说明Minecraft附魔系统，包括所有附魔效果、获取方式和最佳搭配",
        dimensions: "介绍下界（Nether）和末地（End）的探索攻略，包含资源获取和Boss打法",
        farming: "讲解Minecraft农业系统，包括所有作物种植、动物繁殖和自动农场设计",
        brewing: "列出Minecraft全部药水配方、酿造方法和效果说明",
        building: "分享Minecraft建筑技巧和装饰方案，包括不同风格的设计思路",
    };
    if (prompts[catKey]) {
        sendMessage(prompts[catKey]);
    }
}

// ========== 聊天功能 ==========
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = messageInput.value.trim();
    if (!msg) return;
    sendMessage(msg);
});

function sendMessage(msg) {
    messageInput.value = '';
    messageInput.style.height = 'auto';
    sendBtn.disabled = true;
    
    addMessage(msg, 'user');
    hideWelcome();
    showTyping();
    
    fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            message: msg,
            session_id: sessionId,
            use_knowledge_base: useRagToggle.checked
        })
    })
    .then(r => r.json())
    .then(d => {
        hideTyping();
        if (d.success) {
            addMessage(d.response, 'bot', d.sources, d.used_rag, {engine: d.engine, confidence: d.confidence});
        } else {
            addMessage('[错误] ' + (d.error || '未知错误'), 'error');
        }
    })
    .catch(e => {
        hideTyping();
        addMessage('[网络错误] 无法连接到服务器，请检查服务是否正常运行', 'error');
    });
}

function askQuick(text) {
    sendMessage(text);
}

function addMessage(content, type, sources=null, usedRag=false, engineInfo=null) {
    const div = document.createElement('div');
    div.className = `msg-bubble ${type}`;
    
    const avatar = type === 'user' ? '🧑' : type === 'error' ? '⚠️' : '⛏️';
    let extra = '';
    
    // 引擎标签
    if (engineInfo) {
        const engineTag = engineInfo.engine === 'MC-RuleEngine'
            ? '<span class="engine-tag mc-engine">MC引擎</span>'
            : '<span class="engine-tag chat-engine">ChatBrain</span>';
        extra += `<div class="source-tags">${engineTag}`;
        if (engineInfo.confidence > 0) {
            extra += ` <span style="font-size:10px;opacity:0.7">MC置信度:${(engineInfo.confidence*100).toFixed(0)}%</span>`;
        }
        extra += '</div>';
    }
    
    if (sources && sources.length > 0 && usedRag) {
        const badges = sources.map(s => `<span class="src-badge">${esc(s)}</span>`).join('');
        extra += `<div class="source-tags">📚 参考: ${badges}</div>`;
    }
    
    div.innerHTML = `
        <div class="msg-avatar">${avatar}</div>
        <div>
            <div class="msg-body ${type === 'error' ? '' : ''}">${esc(content)}</div>
            ${extra}
        </div>
    `;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function showTyping() {
    const div = document.createElement('div');
    div.className = 'msg-bubble bot';
    div.id = 'typingTemp';
    div.innerHTML = `
        <div class="msg-avatar">⛏️</div>
        <div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>
    `;
    messagesContainer.appendChild(div);
    scrollToBottom();
}
function hideTyping() { const el = document.getElementById('typingTemp'); if(el) el.remove(); }

function hideWelcome() {
    const el = messagesContainer.querySelector('.welcome-screen');
    if (el) el.remove();
}

async function clearChat() {
    if(!confirm('确定清空对话历史？')) return;
    await fetch('/api/clear', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId})});
    messagesContainer.innerHTML = `
        <div class="welcome-screen">
            <div class="welcome-block mc-block grass">
                <span class="welcome-emoji">⛏️</span>
                <h2>对话已清空</h2>
                <p>有什么可以帮你的？</p>
            </div>
            <div class="quick-actions">
                <p class="quick-label">试试问我：</p>
                <div class="quick-cards">
                    <button class="quick-card mc-block stone" onclick="askQuick('钻石剑怎么合成？')">⚔️ 钻石剑怎么合成？</button>
                    <button class="quick-card mc-block dirt" onclick="askQuick('红石中继器用法')">⚡ 红石中继器用法</button>
                    <button class="quick-card mc-block nether" onclick="askQuick('召唤凋灵')">💀 召唤凋灵</button>
                    <button class="quick-card mc-block oak" onclick="askQuick('附魔技巧')">✨ 附魔技巧</button>
                </div>
            </div>
        </div>`;
    sessionId = 'mc_' + Date.now();
}

function esc(t) { const d=document.createElement('div'); d.textContent=t; return d.innerHTML; }

messageInput.addEventListener('keydown', e => {
    if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); chatForm.dispatchEvent(new Event('submit')); }
});

// ========== 知识库 ==========
function setupUpload() {
    fileInput.onchange = handleFiles;
    uploadArea.ondragover = e => { e.preventDefault(); uploadArea.classList.add('drag-over'); };
    uploadArea.ondragleave = () => uploadArea.classList.remove('drag-over');
    uploadArea.ondrop = e => {
        e.preventDefault(); uploadArea.classList.remove('drag-over');
        fileInput.files=e.dataTransfer.files; handleFiles({target:fileInput});
    };
}

async function handleFiles(ev) {
    const files=ev.target.files; if(!files.length) return;
    uploadProgress.classList.remove('hidden');
    
    for(let i=0;i<files.length;i++){
        const f=files[i];
        const fd=new FormData(); fd.append('file',f);
        uploadProgress.textContent=`处理中: ${f.name} (${i+1}/${files.length})`;
        try{
            const r=await fetch('/api/knowledge/upload',{method:'POST',body:fd});
            const d=await r.json();
            uploadProgress.textContent=d.success?`✓ ${d.name} - ${d.chunks_count}片`:`✗ ${d.error}`;
        }catch{ uploadProgress.textContent=`✗ 网络: ${f.name}`;}
    }
    setTimeout(()=>{ uploadProgress.classList.add('hidden'); loadKbStats(); },1200);
    fileInput.value='';
}

async function loadKbStats(){
    try{
        const r=await fetch('/api/knowledge/stats');
        const d=await r.json();
        chunkCountEl.textContent=d.total_documents||0;
        docCountEl.textContent=d.sources?Object.keys(d.sources).length:0;
        if(d.sources) renderFileList(d.sources);
    }catch{}
}

function renderFileList(sources){
    if(!sources||!Object.keys(sources).length){
        fileListEl.innerHTML='<div class="empty-hint">暂无自定义文档</div>';
        return;
    }
    fileListEl.innerHTML=Object.entries(sources).map(([name,count])=>`
        <div class="file-item-mc">
            <span class="file-name-mc"><span>📄</span><span title="${esc(name)}">${esc(name)}</span></span>
            <span class="file-type-badge">${count}片</span>
            <button class="del-file-btn" onclick="delFile('${encodeURIComponent(name)}')" title="删除">×</button>
        </div>
    `).join('');
}

async function delFile(src){
    if(!confirm(`确定删除 "${decodeURIComponent(src)}"？`))return;
    try{
        const r=await fetch(`/api/knowledge/${src}`,{method:'DELETE'});
        if((await r.json()).success) loadKbStats();
    }catch{}
}

async function clearKB(){
    if(!confirm('确定重置知识库？（内置MC数据会保留）'))return;
    try{
        await fetch('/api/knowledge/clear',{method:'POST'});
        fileListEl.innerHTML='<div class="empty-hint">已重置</div>';
        loadKbStats();
    }catch{}
}

function scrollToBottom(){ messagesContainer.scrollTop=messagesContainer.scrollHeight; }
