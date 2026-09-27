"""
轻量级知识库 - 纯Python实现，无重型依赖
使用BM25关键词匹配算法替代向量检索
"""

import os
import re
import json
import math
import jieba
from collections import defaultdict, Counter

import config


class BM25:
    """轻量BM25搜索引擎（纯Python实现）"""
    
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avg_dl = 0  # 平均文档长度
        self.doc_freqs = defaultdict(int)  # 词频文档数 df
        self.doc_lens = []  # 各文档长度
        self.tf = []  # 各文档的词频 {word: count}
        self.docs = []  # 原始文本
        self.metadatas = []  # 元数据
        self.idf = {}  # 逆文档频率
    
    def add_documents(self, documents: list, metadatas: list = None):
        """添加文档"""
        for i, doc in enumerate(documents):
            tokens = list(jieba.cut_for_search(doc.lower()))
            tf = Counter(tokens)
            self.tf.append(tf)
            self.doc_lens.append(len(tokens))
            self.docs.append(doc)
            
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            self.metadatas.append(meta)
            
            for word in set(tokens):
                self.doc_freqs[word] += 1
        
        self.doc_count += len(documents)
        self.avg_dl = sum(self.doc_lens) / max(self.doc_count, 1)
        
        # 计算IDF
        N = max(self.doc_count, 1)
        for word, df in self.doc_freqs.items():
            self.idf[word] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
    
    def search(self, query: str, top_k: int = 5) -> list:
        """搜索相关文档"""
        if not self.docs:
            return []
        
        query_tokens = list(jieba.cut_for_search(query.lower()))
        scores = []
        
        for doc_idx in range(self.doc_count):
            score = 0.0
            dl = self.doc_lens[doc_idx]
            
            for token in set(query_tokens):
                if token not in self.idf:
                    continue
                
                idf = self.idf[token]
                tf_val = self.tf[doc_idx].get(token, 0)
                
                # BM25评分公式
                numerator = tf_val * (self.k1 + 1)
                denominator = tf_val + self.k1 * (1 - self.b + self.b * dl / max(self.avg_dl, 1))
                score += idf * numerator / denominator
            
            if score > 0:
                scores.append((doc_idx, score))
        
        # 排序返回top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for idx, s in scores[:top_k]:
            results.append({
                "content": self.docs[idx],
                "metadata": self.metadatas[idx],
                "score": round(s, 4),
                "index": idx
            })
        
        return results
    
    def delete_by_source(self, source: str) -> int:
        """删除指定来源的文档"""
        indices_to_remove = [i for i, m in enumerate(self.metadatas) 
                           if m.get('source') == source]
        if not indices_to_remove:
            return 0
        
        # 从后往前删除避免索引错位
        for idx in sorted(indices_to_remove, reverse=True):
            del self.docs[idx]
            del self.metadatas[idx]
            del self.doc_lens[idx]
            del self.tf[idx]
            self.doc_count -= 1
        
        # 重新计算统计信息
        if self.docs:
            self.avg_dl = sum(self.doc_lens) / max(self.doc_count, 1)
        else:
            self.avg_dl = 0
            self.doc_freqs.clear()
            self.idf.clear()
        
        return len(indices_to_remove)
    
    def clear(self):
        """清空所有数据"""
        self.doc_count = 0
        self.avg_dl = 0
        self.doc_freqs = defaultdict(int)
        self.doc_lens = []
        self.tf = []
        self.docs = []
        self.metadatas = []
        self.idf = {}
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        sources = Counter()
        for m in self.metadatas:
            src = m.get('source', 'unknown')
            sources[src] += 1
        
        return {
            "total_documents": self.doc_count,
            "sources": dict(sources),
            "search_engine": "BM25"
        }
    
    def to_json(self) -> str:
        """序列化为JSON（用于持久化）"""
        data = {
            "docs": self.docs,
            "metadatas": self.metadatas,
            "doc_lens": self.doc_lens,
            "tf": [dict(t) for t in self.tf],
            "doc_freqs": dict(self.doc_freqs),
            "avg_dl": self.avg_dl,
            "doc_count": self.doc_count,
            "idf": self.idf
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str):
        """从JSON反序列化"""
        data = json.loads(json_str)
        engine = cls.__new__(cls)
        engine.docs = data.get("docs", [])
        engine.metadatas = data.get("metadatas", [])
        engine.doc_lens = data.get("doc_lens", [])
        engine.tf = [Counter(t) for t in data.get("tf", [])]
        engine.doc_freqs = defaultdict(int, data.get("doc_freqs", {}))
        engine.avg_dl = data.get("avg_dl", 0)
        engine.doc_count = data.get("doc_count", 0)
        engine.idf = data.get("idf", {})
        return engine


class DocumentProcessor:
    """文档处理器"""
    
    @staticmethod
    def split_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> list:
        """智能分块"""
        if chunk_size is None:
            chunk_size = config.CHUNK_SIZE
        if chunk_overlap is None:
            chunk_overlap = config.CHUNK_OVERLAP
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            if end < len(text):
                break_points = [
                    text.rfind('\n', start, end),
                    text.rfind('。', start, end),
                    text.rfind('.', start, end),
                    text.rfind('，', start, end),
                    text.rfind(',', start, end),
                    text.rfind(' ', start, end),
                ]
                break_points = [bp for bp in break_points if bp > start]
                if break_points:
                    end = max(break_points) + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - chunk_overlap
        
        return chunks
    
    @staticmethod
    def process_pdf(file_path: str) -> str:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        texts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
        return '\n'.join(texts)
    
    @staticmethod
    def process_docx(file_path: str) -> str:
        from docx import Document
        doc = Document(file_path)
        texts = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n'.join(texts)
    
    @staticmethod
    def process_txt(file_path: str) -> str:
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        raise Exception("无法识别文件编码")
    
    @classmethod
    def process_file(cls, file_path: str) -> tuple:
        ext = os.path.splitext(file_path)[1].lower()
        handlers = {
            '.txt': cls.process_txt,
            '.md': cls.process_txt,
            '.pdf': cls.process_pdf,
            '.docx': cls.process_docx,
        }
        handler = handlers.get(ext)
        if not handler:
            raise Exception(f"不支持的格式: {ext}，支持 .txt/.md/.pdf/.docx")
        content = handler(file_path)
        return content, ext[1:]
