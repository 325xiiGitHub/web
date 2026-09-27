"""
方块君AI引擎 v2.0 - 自建混合模型
A部分: 规则引擎 (Minecraft专家，关键词匹配+知识库+模板回复)
B部分: 内置小模型 (通用对话，语义理解+上下文记忆+模板生成)
无需任何外部LLM服务，纯本地运行！
"""

import re
import random
import json
import os
import hashlib
import time
from collections import defaultdict, Counter
import jieba
import config


# ============================================================
#  A部分: Minecraft 规则引擎 (专家系统)
# ============================================================

# MC关键词映射 -> 知识库搜索增强
MC_KEYWORDS = {
    # 合成相关
    "合成": ["crafting", "recipe", "合成表", "工作台"],
    "配方": ["recipe", "配方", "合成"],
    "工作台": ["crafting_table", "工作台", "合成台"],
    "熔炉": ["furnace", "熔炉", "冶炼", "烧炼"],
    "锻造": ["smithing", "锻造", "下界合金", "netherite"],
    "附魔": ["enchanting", "附魔", "附魔台", "经验值", "经验等级"],
    "酿造": ["brewing", "酿造", "药水", "炼药锅"],
    
    # 生物/怪物
    "怪物": ["mob", "monster", "怪物", "怪", "生物"],
    "僵尸": ["zombie", "僵尸", "尸壳", "溺尸"],
    "骷髅": ["skeleton", "骷髅", "流浪者", "凋灵骷髅"],
    "苦力怕": ["creeper", "苦力怕", "爬行者", "JJ怪"],
    "末影人": ["enderman", "末影人", "黑高个", "小黑"],
    "猪灵": ["piglin", "猪灵", "疣猪兽"],
    "守卫者": ["guardian", "守卫者", "远古守卫者"],
    "掠夺者": ["raider", "掠夺者", "劫掠兽", "卫道士"],
    "boss": ["boss", "Boss", "BOSS", "末影龙", "凋灵"],
    "末影龙": ["ender_dragon", "末影龙", "龙"],
    "凋灵": ["wither", "凋灵", "三头boss"],
    "村民": ["villager", "村民", "交易", "职业"],
    "动物": ["animal", "动物", "牛", "羊", "猪", "鸡"],
    
    # 方块/物品
    "红石": ["redstone", "红石", "红石电路", "自动化"],
    "命令方块": ["command_block", "命令方块", "指令", "/give", "/summon"],
    "钻石": ["diamond", "钻石", "矿洞", "挖掘"],
    "下界合金": ["netherite", "下界合金", "最强装备"],
    "基岩": ["bedrock", "基岩", "不可破坏"],
    "黑曜石": ["obsidian", "黑曜石", "下界传送门"],
    "末地": ["end", "末地", "末影之地", "末影珍珠"],
    "下界": ["nether", "下界", "地狱"],
    
    # 游戏机制
    "饥饿": ["hunger", "饥饿", "食物", "饱和度"],
    "生命": ["health", "生命", "血量", "生命值", "治疗"],
    "经验": ["xp", "experience", "经验", "等级"],
    "附魔": ["enchant", "附魔", "诅咒", "铁砧"],
    "药水": ["potion", "药水", "效果", "buff"],
    "进度": ["advancement", "进度", "成就"],
    "难度": ["difficulty", "难度", "和平", "生存"],
    
    # 建筑装饰
    "建筑": ["build", "建筑", "建造", "房子", "设计"],
    "红石": ["redstone", "红石", "电路", "自动机", "农场"],
    "农场": ["farm", "农场", "自动", "刷怪塔"],
}

# 意图识别模式
INTENT_PATTERNS = {
    # 合成查询
    "craft_how": [
        r"怎么合成?(.+)", r"如何制作(.+)", r"(.+)的合成公式",
        r"如何获得(.+)", r"怎么得到(.+)", r"(.+)怎么做",
        r"craft (.+)", r"how to make (.+)", r"how to craft (.+)",
        r"(.+)的配方",
    ],
    # 属性查询  
    "entity_info": [
        r"(.+?)的属性", r"(.+?)的数据", r"(.+?)的血量",
        r"(.+?)的攻击力", r"(.+?)掉落什么", r"关于(.+)",
        r"tell me about (.+)", r"what is (.+)",
    ],
    # 指令查询
    "command_query": [
        r"(.+)指令", r"(.+)命令", r"怎么用指令(.+)",
        r"(/?\w+.*?)(?:的|怎么)?用法?", r"command for (.+)",
        r"how to (.+) with command",
    ],
    # 攻略类
    "strategy": [
        r"怎么打败(.+)", r"如何击败(.+)", r"击败(.+)?的?方法",
        r"如何找到(.+)", r"(.+)在哪里", r"(?:去|到).+?找(.+)",
        r"how to beat (.+)", r"where to find (.+)",
        r"(.+)(?:攻略|打法|技巧|教程)",
    ],
    # 对比类
    "compare": [
        r"(.+?)和(.+?)(?:哪个好|对比|比较|区别|哪个强)",
        r"compare (.+?) and (.+?)", r"(.+?) vs (.+?)",
    ],
    # 列表类
    "list_items": [
        r"列出所有(.+)", r"有哪些(.+)", r"(.+?)(?:列表|一览|大全)",
        r"list of (.+)", r"all (.+)",
    ],
}

# 模板回复池
TEMPLATE_RESPONSES = {
    "greeting": [
        "嘿，冒险者！我是方块君，你的Minecraft专属助手。有什么我可以帮你的吗？⛏️",
        "你好呀！准备好开始新的冒险了吗？问我任何关于Minecraft的问题吧！🎮",
        "方块君上线了！合成、红石、战斗、建筑...尽管问！🟩",
        "欢迎来到方块世界！我是方块君，让我来帮你解决所有MC问题吧~ ⚔️",
    ],
    "greeting_mc": [
        "哟，又来挖矿了吗？今天想了解点什么？🎮",
        "冒险者你好！有什么MC问题尽管问，我的知识库里啥都有！💎",
        "嘿！是时候建造点什么东西了吗？还是想挑战某个Boss？😎",
    ],
    "unknown": [
        "嗯...这个问题有点超出我的知识范围了 😅 不过作为Minecraft专家，我更擅长回答游戏相关问题哦！你可以试试问我：\n• \"钻石剑怎么合成？\"\n• \"末影龙怎么打？\"\n• \"红石中继器怎么用？\"",
        "这个话题我不太擅长呢...但如果你问的是Minecraft的问题，我肯定能帮到你！💡\n\n比如：\n- 合成配方查询\n- 怪物属性数据\n- 红石电路设计\n- 指令使用方法",
        "抱歉，我对这个话题了解有限 🤔 但在Minecraft领域，我就是百科全书！换个MC相关的问题试试？",
    ],
    "thinking": [
        "让我想想... 🤔",
        "正在查阅我的MC知识库... 📚",
        "好问题！让我找找答案... 🔍",
        "嗯，这个问题我知道！✨",
    ],
    "thanks": [
        "不客气！祝你挖矿不掉岩浆，探险不掉虚空！🎉",
        "能帮到你就好！继续冒险吧，冒险者！⚔️",
        "随时回来找我，我一直在这里等你~ 💎",
        "有其他问题随时问，方块君24小时在线！🌟",
    ],
    "farewell": [
        "再见啦，冒险者！记得早点回家睡觉（现实里的）😴🏠",
        "下次见！愿你的背包永远装得下宝藏！🎒💰",
        "拜拜！记得常回来看看~ 方块君会想你的！👋",
    ],
}


class MCEngine:
    """
    Minecraft 规则引擎 (A部分)
    通过关键词匹配、意图识别、知识库检索生成专业回答
    """
    
    def __init__(self):
        self.knowledge_base = None
    
    def set_kb(self, kb):
        """设置知识库引用"""
        self.knowledge_base = kb
    
    def is_mc_related(self, text: str) -> tuple[bool, float]:
        """判断是否与MC相关，返回(是否相关, 置信度)"""
        text_lower = text.lower()
        
        # 直接MC关键词检测
        mc_terms = [
            "minecraft", "mc", "minecraf", "我的世界", "方块", "史蒂夫",
            "alex", "creeper", "苦力怕", "僵尸", "末影", "下界", "地狱",
            "合成", "熔炉", "工作台", "钻石", "铁", "金", "红石", "附魔",
            "药水", "经验", "等级", "血量", "攻击", "防御", "盔甲", "武器",
            "工具", "镐", "斧", "锹", "剑", "弓", "盾", "鞘翅", "三叉戟",
            "末影龙", "凋灵", "守卫者", "掠夺者", "村民", "猪灵",
            "指令", "命令方块", "数据包", "mod", "模组", "服务器",
            "生存", "创造", "冒险", "旁观", "硬度", "难度", "生物群系",
            "村庄", "要塞", "废弃传送门", "堡垒遗迹", "末地城", "下界要塞",
            "/give", "/summon", "/tp", "/gamemode", "/kill",
            "tnt", "tnt", "床", "重生锚", " respawn",
            "steve", "herobrine", "notch", "mojang",
            "java版", "基岩版", "版本",
            "小麦", "胡萝卜", "马铃薯", "种植", "养殖",
            "锻造", "磨石", "砂轮", "箭台", "织布机",
            "盾构", "侦测器", "比较器", "活塞", "粘性活塞",
            "漏斗", "投掷器", "发射器", "矿车", "铁轨",
            "海晶灯", "萤石", " glowstone", "slime_block",
        ]
        
        score = 0
        found_terms = []
        for term in mc_terms:
            if term in text_lower:
                score += 2
                found_terms.append(term)
        
        # 检测中文MC特有词
        mc_cn_patterns = [
            r"[拔挖]草", r"撸树", r"挖矿", r"打怪", r"盖房",
            r"下矿", r"联机", r"单机", r"生存模式", r"创造模式",
            r"主世界", r"末路之地", r"下界",
            r"\d+\.\d+(\.\d+)?(?:\.?\d*)?",  # 版本号如1.20.4
        ]
        for p in mc_cn_patterns:
            if re.search(p, text):
                score += 1
        
        return (score >= 1, min(score / 5.0, 1.0))
    
    def detect_intent(self, text: str) -> str:
        """识别用户意图"""
        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return intent
        return "general"
    
    def generate_response(self, message: str, kb_results: list = None) -> str | None:
        """
        生成MC专业回答
        返回None表示无法处理，交给B部分处理
        """
        is_mc, confidence = self.is_mc_related(message)
        if not is_mc or confidence < 0.3:
            return None
        
        intent = self.detect_intent(message)
        
        # 如果有知识库结果，基于KB构建答案
        if kb_results:
            return self._build_kb_response(message, kb_results, intent)
        
        # 无KB结果时，用规则生成回答
        return self._rule_based_response(message, intent, confidence)
    
    def _build_kb_response(self, message: str, results: list, intent: str) -> str:
        """基于知识库检索结果构建结构化回答"""
        intro = random.choice(TEMPLATE_RESPONSES["thinking"])
        
        # 取最相关的结果
        top_result = results[0]
        content = top_result["content"]
        source = top_result.get("metadata", {}).get("source", "知识库")
        score = top_result.get("score", 0)
        
        # 根据意图格式化回答
        if intent == "craft_how":
            response = f"{intro}\n\n"
            response += f"## 📋 {message.strip()}\n\n"
            
            # 提取所有相关知识
            all_content = "\n---\n".join([r["content"][:500] for r in results[:3]])
            response += f"{all_content}\n\n"
            response += f"*来源: {source} | 相关度: {score}*\n"
            
        elif intent == "entity_info":
            response = f"{intro}\n\n"
            for i, r in enumerate(results[:3]):
                src = r.get("metadata", {}).get("source", "?")
                response += f"### [{src}] {r['content'][:300]}\n\n"
                
        elif intent == "command_query":
            response = f"{intro}\n\n## 💻 指令参考\n\n"
            for r in results[:3]:
                cmd_match = re.search(r'(/[a-zA-Z_]+[^`\n]*)', r['content'])
                if cmd_match:
                    response += f"`{cmd_match.group(1)}`\n"
                    desc = r['content'][:200]
                    response += f"> {desc}\n\n"
                    
        elif intent == "strategy":
            response = f"{intro}\n\n## ⚔️ 攻略指南\n\n"
            for i, r in enumerate(results[:3]):
                response += f"**{i+1}.** {r['content'][:400]}\n\n"
            response += "---\n*以上信息来自MC知识库，祝你成功！* 🍀\n"
            
        else:
            # 通用KB回答
            response = f"{intro}\n\n"
            for i, r in enumerate(results[:3]):
                src = r.get("metadata", {}).get("source", "?")
                response += f"**[{src}]**\n{r['content'][:350]}\n\n"
        
        return response
    
    def _rule_based_response(self, message: str, intent: str, confidence: float) -> str:
        """无KB匹配时的规则回答"""
        intro = random.choice(TEMPLATE_RESPONSES["thinking"])
        
        # 问候
        greetings = ["你好", "嗨", "hi", "hello", "嘿", "在吗"]
        if any(g in message.lower() for g in greetings):
            return random.choice(TEMPLATE_RESPONSES["greeting_mc"])
        
        # 感谢
        thanks_words = ["谢谢", "感谢", "thx", "thanks", "多谢"]
        if any(t in message for t in thanks_words):
            return random.choice(TEMPLATE_RESPONSES["thanks"])
        
        # 再见
        bye_words = ["再见", "拜拜", "bye", "goodbye", "溜了", "走了"]
        if any(b in message for b in bye_words):
            return random.choice(TEMPLATE_RESPONSES["farewell"])
        
        # 默认：说明知识库没有精确匹配，给出建议
        return (
            f"{intro}\n\n"
            f"我在知识库里没找到完全匹配的内容，但根据你的问题「{message[:50]}」，"
            f"这看起来是个MC相关的问题！(置信度: {confidence:.0%})\n\n"
            f"**建议你：**\n"
            f"1. 上传相关文档到知识库，我会学习后回答\n"
            f"2. 换种方式提问，比如具体说明你想知道什么\n"
            f"3. 或者试试问一些基础问题：\"钻石怎么合成\"、\"红石怎么用\"\n\n"
            f"我的知识库目前包含 {self._kb_count()} 条MC知识记录 ✨"
        )
    
    def _kb_count(self) -> int:
        try:
            if self.knowledge_base:
                return self.knowledge_base.doc_count
        except:
            pass
        return 0


# ============================================================
#  B部分: 内置聊天模型 (ChatBrain)
# ============================================================

class ChatBrain:
    """
    内置轻量聊天模型 (B部分)
    特性：
    - 上下文感知对话
    - 情绪/语气识别
    - 主题追踪
    - 模板化自然回复生成
    - 无需GPU，纯CPU推理
    """
    
    # 话题关键词网络
    TOPIC_NETWORK = {
        "游戏": ["游戏", "game", "玩", "play", "好玩", "有趣", "无聊"],
        "编程": ["代码", "code", "程序", "python", "编程", "开发", "bug", "写"],
        "生活": ["吃饭", "睡", "累", "忙", "休息", "天气", "今天", "心情"],
        "学习": ["学习", "考试", "作业", "学校", "看书", "知识", "不懂"],
        "音乐": ["歌", "music", "听歌", "音乐", "歌手", "band"],
        "电影": ["电影", "movie", "番剧", "动漫", "动画", "剧"],
        "技术": ["ai", "人工智能", "模型", "算法", "训练", "神经网络"],
    }
    
    # 回复模板库
    RESPONSE_TEMPLATES = {
        "question_general": [
            "这是个好问题！我觉得{topic_comment}。你觉得呢？",
            "嗯...让我想想。{topic_comment} 你怎么看？",
            "{topic_comment} 这个问题挺有意思的。",
            "说实话我也不太确定，但{topic_comment}。要不我们一起探索一下？",
        ],
        "statement_agree": [
            "同意！{expand}",
            "没错没错，{expand}",
            "太对了！{expand}",
            "我也这么觉得！{expand}",
            "说得好！{expand}",
        ],
        "statement_neutral": [
            "原来如此，{expand}",
            "这样啊，{expand}",
            "了解了，{expand}",
            "嗯嗯，{expand}",
            "有意思的观点，{expand}",
        ],
        "emotion_positive": [
            "听起来很棒！{encourage}",
            "哇，太好了！{encourage}",
            "为你开心！🎉 {encourage}",
            "nice！{encourage}",
        ],
        "emotion_negative": [
            "别太难过了，{comfort}",
            "抱抱你 🤗 {comfort}",
            "没事的，一切都会好的！{comfort}",
            "理解你的感受... {comfort}",
        ],
        "confused": [
            "呃...你能再说详细一点吗？我没太理解 😅",
            "这个...有点超纲了哈哈，能解释一下吗？",
            "嗯？没太听懂，换个说法？",
            "我的CPU转了一下，但还是不太明白，能展开说说吗？",
        ],
        "curious": [
            "哦？展开说说！我很感兴趣 👀",
            "真的假的？快告诉我更多细节！",
            "咦？这倒是有意思，然后呢？",
            "等等，我想听听完整的故事！",
        ],
        "joking": [
            "哈哈哈 你真幽默 😂",
            "噗 笑死我了",
            "哈哈哈哈 这也太搞笑了",
            "你是懂搞笑的 🤣",
        ],
        "opinion_asked": [
            "我个人觉得{opinion}，不过每个人的看法都不一样~",
            "从我的角度来看，{opinion}",
            "嗯...如果非要我说的话，{opinion}",
            "这是个见仁见智的问题，但我倾向于{opinion}",
        ],
    }
    
    # 话题扩展内容
    TOPIC_EXPANDS = {
        "游戏": [
            "游戏确实是很好的放松方式呢",
            "最近有没有玩什么新游戏？",
            "说到游戏，Minecraft可是经典中的经典！",
            "适度游戏益脑，过度伤身哦~",
            "你平时喜欢什么类型的游戏？",
        ],
        "编程": [
            "编程是一件很有成就感的事情！",
            "Python是个很好的入门语言",
            "遇到bug不要慌，冷静分析就能解决",
            "写代码就像解谜一样，很有趣",
            "我也是用Python写的哦~",
        ],
        "生活": [
            "生活嘛，开心最重要啦",
            "要注意劳逸结合哦",
            "身体健康是革命的本钱！",
            "今天过得怎么样？",
            "好好照顾自己~",
        ],
        "学习": [
            "学习是一辈子的事",
            "不懂就问，没什么丢人的",
            "循序渐进，慢慢来就好",
            "知识就是力量！",
            "保持好奇心是最好的学习方法",
        ],
        "default": [
            "继续聊聊？",
            "然后呢？",
            "还有别的想说的吗？",
            "我很乐意听你分享~",
            "这个话题挺有趣的",
        ],
    }
    
    def __init__(self, name: str = "方块君"):
        self.name = name
        self.conversation_memory = []  # 短期记忆
        self.max_memory = 10
        self.user_profile = {}  # 用户画像
    
    def detect_topic(self, text: str) -> list[str]:
        """检测文本涉及的话题"""
        text_lower = text.lower()
        detected = []
        for topic, keywords in self.TOPIC_NETWORK.items():
            if any(kw in text_lower for kw in keywords):
                detected.append(topic)
        return detected if detected else ["default"]
    
    def detect_emotion(self, text: str) -> str:
        """检测情绪倾向"""
        positive_words = ["开心", "高兴", "棒", "厉害", "牛", "赞", "爱", "喜欢", 
                         "happy", "great", "awesome", "cool", "nice", "哈哈", "嘻嘻",
                         "😊", "😄", "🎉", "❤️", "👍", "🔥", "💪"]
        negative_words = ["难过", "伤心", "烦", "讨厌", "累", "痛", "烦人", "崩溃",
                         "sad", "angry", "tired", "hate", "bad", "terrible", "😢", "😭", "😡"]
        question_marks = text.count("？") + text.count("?")
        exclaim = text.count("！") + text.count("!")
        laugh = len(re.findall(r'哈{2,}|呵呵|haha|lol|lmao|xdl', text_lower := text.lower()))
        
        p_score = sum(1 for w in positive_words if w in text_lower)
        n_score = sum(1 for w in negative_words if w in text_lower)
        
        if laugh >= 2:
            return "joking"
        if question_marks > 0 and exclaim > question_marks:
            return "curious"
        if p_score > n_score + 1:
            return "positive"
        if n_score > p_score + 1:
            return "negative"
        if question_marks > 0:
            return "question"
        return "neutral"
    
    def classify_message_type(self, text: str, emotion: str) -> str:
        """分类消息类型"""
        text_stripped = text.strip()
        
        # 问句判断
        if re.search(r'[？?]$', text_stripped) or re.search(r'^(什么|怎么|哪|谁|为什么|咋|如何|who|what|when|where|why|how)', text_stripped):
            if emotion == "question":
                topics = self.detect_topic(text)
                if "default" not in topics or len(text) > 6:
                    return "question_topic"
                return "question_general"
            return "question_general"
        
        # 表达观点/陈述
        if emotion == "positive":
            return "emotion_positive"
        if emotion == "negative":
            return "emotion_negative"
        if emotion == "joking":
            return "joking"
        if emotion == "curious":
            return "curious"
        
        # 寻求意见
        if re.search(r'(?:觉得|认为|看法|想法|think|opinion|怎么样|如何|好不好)', text):
            return "opinion_asked"
        
        return "statement_neutral"
    
    def _generate_opinion(self, topic: str) -> str:
        """生成意见"""
        opinion_templates = {
            "游戏": "游戏可以让人放松身心，也能锻炼反应能力",
            "编程": "编程是一项非常实用的技能，值得深入学习",
            "生活": "享受当下、保持积极的心态很重要",
            "学习": "持续学习是进步的关键",
            "default": "这是一个值得思考的话题",
        }
        base = opinion_templates.get(topic, opinion_templates["default"])
        variants = [base,
                   f"关于这个，{base}",
                   f"我认为{base}"]
        return random.choice(variants)
    
    def _generate_expand(self, topic: str) -> str:
        """生成扩展内容"""
        expands = self.TOPIC_EXPANDS.get(topic, self.TOPIC_EXPANDS["default"])
        return random.choice(expands)
    
    def generate_response(self, message: str, history: list = None) -> str:
        """生成聊天回复 (B部分核心)"""
        # 更新记忆
        self.conversation_memory.append({"role": "user", "content": message})
        if len(self.conversation_memory) > self.max_memory * 2:
            self.conversation_memory = self.conversation_memory[-self.max_memory * 2:]
        
        emotion = self.detect_emotion(message)
        msg_type = self.classify_message_type(message, emotion)
        topics = self.detect_topic(message)
        primary_topic = topics[0] if topics else "default"
        
        # 根据消息类型选择模板并填充
        templates = self.RESPONSE_TEMPLATES.get(msg_type, self.RESPONSE_TEMPLATES["statement_neutral"])
        template = random.choice(templates)
        
        # 填充模板变量
        response = template.format(
            topic_comment=f"关于{'/'.join(topics)}这个话题",
            expand=self._generate_expand(primary_topic),
            encourage="继续保持这种状态！",
            comfort="有什么我能帮忙的吗？",
            opinion=self._generate_opinion(primary_topic),
        )
        
        # 加入自我介绍前缀（偶尔）
        if random.random() < 0.05 and primary_topic != "游戏":
            response = f"({self.name}悄悄说: 我其实更擅长Minecraft问题~)\n\n{response}"
        
        # 记录回复到记忆
        self.conversation_memory.append({"role": "assistant", "content": response})
        
        return response
    
    def reset_memory(self):
        """重置对话记忆"""
        self.conversation_memory = []


# ============================================================
#  混合引擎 (HybridEngine)
# ============================================================

class HybridAI:
    """
    A+B 混合AI引擎
    - A: MC规则引擎优先处理MC相关问题
    - B: 聊天模型处理通用对话
    - 自动路由，智能切换
    """
    
    def __init__(self):
        self.mc_engine = MCEngine()
        self.chat_brain = ChatBrain("方块君")
        self.use_kb = True
        self.stats = {"mc_engine": 0, "chat_brain": 0, "total": 0}
    
    def set_knowledge_base(self, kb):
        """设置知识库"""
        self.mc_engine.set_kb(kb)
        self._kb = kb
    
    async def chat(self, message: str, history: list = None, 
                   knowledge_context: list = None) -> dict:
        """
        统一聊天接口
        返回: {"response": str, "engine": str, "sources": list}
        """
        self.stats["total"] += 1
        message = message.strip()
        if not message:
            return {"response": "你还没说话呢~ 说点什么吧！", "engine": "system"}
        
        # Step 1: 尝试MC规则引擎 (A部分)
        is_mc, mc_confidence = self.mc_engine.is_mc_related(message)
        
        kb_results = None
        if is_mc and self.use_kb and hasattr(self, '_kb') and self._kb:
            try:
                kb_results = self._kb.search(message, top_k=4)
                kb_results = [r for r in kb_results if r.get("score", 0) > 0.1]
            except Exception as e:
                print(f"[KB搜索出错] {e}")
        
        # 高置信度MC问题 → A部分
        if is_mc and mc_confidence >= 0.25:
            mc_response = self.mc_engine.generate_response(message, kb_results)
            if mc_response:
                self.stats["mc_engine"] += 1
                sources = []
                if kb_results:
                    sources = list(set(
                        r.get("metadata", {}).get("source", "?") 
                        for r in (kb_results or [])
                    ))
                return {
                    "response": mc_response,
                    "engine": "MC-RuleEngine",
                    "confidence": round(mc_confidence, 2),
                    "sources": sources,
                    "used_rag": bool(kb_results),
                }
        
        # Step 2: 走通用聊天 (B部分)
        response = self.chat_brain.generate_response(message, history)
        self.stats["chat_brain"] += 1
        
        # 如果是低置信度的MC问题，追加小提示
        if is_mc and mc_confidence < 0.25:
            response += "\n\n> 💡 *提示: 我检测到这可能跟Minecraft有关，上传更多文档到知识库后我能回答得更专业！*"
        
        return {
            "response": response,
            "engine": "ChatBrain-B",
            "confidence": round(mc_confidence, 2) if is_mc else 0,
            "sources": [],
            "used_rag": False,
        }
    
    async def check_connection(self) -> dict:
        """检查状态 (兼容旧接口)"""
        return {
            "connected": True,
            "model": "Hybrid-A+B(v2.0)",
            "models": ["MC-RuleEngine", "ChatBrain-B"],
            "current_model": "Hybrid-A+B",
            "model_available": True,
            "stats": self.stats,
        }
    
    def clear_session(self, session_id: str = None):
        """清除会话"""
        self.chat_brain.reset_memory()


# 全局实例
hybrid_ai = HybridAI()
