"""
方块君 v4.0 - 自建混合AI引擎 (A+B)
A: MC规则引擎 | B: 内置聊天模型 | 无需外部LLM服务
"""

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import json
import uvicorn

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="方块君 - Minecraft AI", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

chat_histories = {}
kb_engine = None
hybrid_ai = None  # 混合AI引擎


def get_hybrid_ai():
    """获取/初始化混合AI引擎"""
    global hybrid_ai, kb_engine
    if hybrid_ai is None:
        from llm_service import HybridAI
        hybrid_ai = HybridAI()
        # 绑定知识库
        kb = get_kb()
        hybrid_ai.set_knowledge_base(kb)
        print(f"[OK] 混合引擎就绪 | 知识库: {kb.doc_count}条记录")
    return hybrid_ai


def get_kb():
    global kb_engine
    if kb_engine is None:
        from knowledge_base import BM25
        kb_path = config.KNOWLEDGE_DB_PATH
        
        if os.path.exists(kb_path):
            try:
                with open(kb_path, 'r', encoding='utf-8') as f:
                    kb_engine = BM25.from_json(f.read())
                return kb_engine
            except:
                pass
        
        # 新建知识库并导入MC数据
        kb_engine = BM25()
        try:
            from mc_data import init_minecraft_knowledge_base
            count = init_minecraft_knowledge_base(kb_engine)
            save_kb()
            print(f"[OK] MC知识库加载完成: {count}条")
        except Exception as e:
            print(f"[!] MC知识库初始化失败: {e}")
    
    return kb_engine


def save_kb():
    if kb_engine:
        with open(config.KNOWLEDGE_DB_PATH, 'w', encoding='utf-8') as f:
            f.write(kb_engine.to_json())


# ========== 路由 ==========

@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(STATIC_DIR, "index.html"), 'r', encoding='utf-8') as f:
        return f.read()


class ChatReq(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    use_knowledge_base: Optional[bool] = True


@app.post("/api/chat")
async def chat(req: ChatReq):
    try:
        ai = get_hybrid_ai()
        
        sid = req.session_id
        if sid not in chat_histories:
            chat_histories[sid] = []
        
        chat_histories[sid].append({"role": "user", "content": req.message})
        
        # 获取知识库结果（供混合引擎使用）
        kb_results = []
        if req.use_knowledge_base:
            try:
                kb = get_kb()
                kb_results = kb.search(req.message, top_k=4)
            except Exception as e:
                print(f"KB搜索异常: {e}")
        
        history = [m for m in chat_histories[sid][:-1] if m["role"] in ("user","assistant")]
        
        # 调用混合AI引擎
        result = await ai.chat(req.message, history, kb_results)
        
        text = result["response"]
        sources_used = result.get("sources", [])
        used_engine = result.get("engine", "?")
        
        chat_histories[sid].append({"role": "assistant", "content": text})
        
        return JSONResponse({
            "success": True,
            "response": text,
            "sources": sources_used,
            "used_rag": result.get("used_rag", False),
            "engine": used_engine,
            "confidence": result.get("confidence", 0),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/clear")
async def clear_history(request: Request):
    data = await request.json()
    chat_histories.pop(data.get("session_id","default"), None)
    return JSONResponse({"success": True})


@app.get("/api/status")
async def status():
    ai_info = {"connected": False, "engine": "Hybrid-A+B", "model": "自建模型v4.0"}
    try:
        ai = get_hybrid_ai()
        ai_info = await ai.check_connection()
    except Exception as e:
        ai_info["error"] = str(e)
    
    kb_stats = {"total_documents": 0, "sources": {}, "search_engine": "BM25+jieba"}
    try:
        kb = get_kb()
        kb_stats = kb.get_stats()
    except:
        pass
    
    return JSONResponse({
        "ai_engine": ai_info,
        "knowledge_base": kb_stats,
        "config": {
            "engine": "Hybrid-A+B (规则引擎 + 聊天模型)",
            "mc_engine": "MCEngine - MC专家规则系统",
            "chat_model": "ChatBrain-B - 内置对话模型",
            "kb_search": "BM25 + jieba中文分词",
            "external_dependency": "无（纯本地运行）"
        }
    })


# ========== 知识库 API ==========

@app.post("/api/knowledge/upload")
async def upload_doc(file: UploadFile = File(...)):
    try:
        from knowledge_base import DocumentProcessor
        dp = DocumentProcessor()
        kb = get_kb()
        
        ext = os.path.splitext(file.filename)[1].lower()
        fid = os.urandom(4).hex()
        save_name = f"{fid}{ext}"
        save_path = os.path.join(config.UPLOAD_DIR, save_name)
        
        content = await file.read()
        with open(save_path, 'wb') as f:
            f.write(content)
        
        text_content, file_type = dp.process_file(save_path)
        
        if not text_content.strip():
            os.remove(save_path)
            return JSONResponse({"success": False, "error": "文件内容为空"})
        
        chunks = dp.split_text(text_content)
        metadatas = [{"source": file.filename, "type": file_type, "fid": fid, "i": i} 
                     for i in range(len(chunks))]
        
        kb.add_documents(chunks, metadatas)
        save_kb()
        
        return JSONResponse({
            "success": True,
            "message": f"导入 {len(chunks)} 个片段",
            "filename": file.filename,
            "chunks_count": len(chunks),
            "file_type": file_type
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/knowledge/stats")
async def kb_stats():
    try:
        kb = get_kb()
        s = kb.get_stats()
        s["enabled"] = True
        return JSONResponse({"success": True, **s})
    except:
        return JSONResponse({"success": True, "total_documents": 0, "sources": {}, "enabled": False})


@app.delete("/api/knowledge/{source:path}")
async def delete_doc(source: str):
    try:
        kb = get_kb()
        n = kb.delete_by_source(source)
        save_kb()
        return JSONResponse({"success": True, "deleted": n})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/knowledge/clear")
async def clear_kb_all():
    try:
        kb = get_kb()
        kb.clear()
        # 重新导入内置知识库
        from mc_data import init_minecraft_knowledge_base
        init_minecraft_knowledge_base(kb)
        save_kb()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ========== MC特色功能 API ==========

@app.get("/api/mc/quick")
async def mc_quick_lookup(q: str):
    """MC快速查询（从内置知识库搜索）"""
    try:
        kb = get_kb()
        results = kb.search(q, top_k=3)
        
        # 过滤出内置文档的结果
        builtin_results = [
            r for r in results 
            if r["metadata"].get("type") == "builtin" and r["score"] > 2.0
        ]
        
        if builtin_results:
            return JSONResponse({
                "success": True,
                "query": q,
                "results": [{
                    "source": r["metadata"]["source"],
                    "content": r["content"][:800],
                    "score": r["score"]
                } for r in builtin_results]
            })
        
        return JSONResponse({
            "success": True,
            "query": q,
            "results": [],
            "hint": "未找到精确匹配，可尝试用聊天提问"
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.get("/api/mc/categories")
async def mc_categories():
    """获取MC知识分类"""
    categories = {
        "crafting": {"name": "合成配方", "icon": "⚒️", "desc": "工具、方块、物品合成表"},
        "mobs": {"name": "怪物生物", "icon": "👾", "desc": "Boss、普通怪、中立生物属性"},
        "commands": {"name": "游戏指令", "icon": "💻", "desc": "/give /summon /gamemode等"},
        "redstone": {"name": "红石工程", "icon": "⚡", "desc": "电路、自动化、机械"},
        "enchanting": {"name": "附魔系统", "icon": "✨", "desc": "附魔台、铁砧、诅咒"},
        "dimensions": {"name": "维度探索", "icon": "🌍", "desc": "下界、末地攻略"},
        "farming": {"name": "农业养殖", "icon": "🌾", "desc": "作物种植、动物繁殖"},
        "brewing": {"name": "药水酿造", "icon": "🧪", "desc": "全部药水配方与效果"},
        "building": {"name": "建筑装饰", "icon": "🏠", "desc": "风格指南、家具DIY、美化技巧"},
    }
    return JSONResponse({"success": True, "categories": categories})


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("=" * 50)
    print("  [方块君] v4.0 - 自建混合AI引擎")
    print("=" * 50)
    print("  A: MC规则引擎 (Minecraft专家)")
    print("  B: ChatBrain (内置聊天模型)")
    print("-" * 50)
    print(f"  访问地址: http://{config.HOST}:{config.PORT}")
    print("  外部依赖: 无 (纯本地运行)")
    print("=" * 50)
    uvicorn.run(app, host=config.HOST, port=config.PORT)
