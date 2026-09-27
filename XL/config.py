import os
from dotenv import load_dotenv

load_dotenv()

# ========== 知识库配置 ==========
KNOWLEDGE_DB_PATH = os.getenv("KNOWLEDGE_DB_PATH", "./data/knowledge.json")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
TOP_K = int(os.getenv("TOP_K", 5))

# ========== 服务配置 ==========
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))

# ========== AI引擎配置 ==========
# A部分: MC规则引擎
MC_CONFIDENCE_THRESHOLD = float(os.getenv("MC_CONFIDENCE_THRESHOLD", "0.25"))
# B部分: 聊天模型
CHAT_MEMORY_SIZE = int(os.getenv("CHAT_MEMORY_SIZE", "10"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
