"""
数据库初始化脚本。

创建数据库表并插入初始数据（英语学习知识点）。
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.session import init_db, async_session
from models.database import Learner, KnowledgeState


# 英语学习初始知识点
INITIAL_KNOWLEDGE_POINTS = [
    # 词汇类
    {"id": "vocab_basic", "name": "基础词汇", "category": "词汇", "difficulty": 0.3},
    {"id": "vocab_intermediate", "name": "中级词汇", "category": "词汇", "difficulty": 0.5},
    {"id": "vocab_advanced", "name": "高级词汇", "category": "词汇", "difficulty": 0.7},
    {"id": "vocab_academic", "name": "学术词汇", "category": "词汇", "difficulty": 0.8},

    # 语法类
    {"id": "grammar_tenses", "name": "时态", "category": "语法", "difficulty": 0.4},
    {"id": "grammar_conditionals", "name": "条件句", "category": "语法", "difficulty": 0.6},
    {"id": "grammar_passive", "name": "被动语态", "category": "语法", "difficulty": 0.5},
    {"id": "grammar_relative", "name": "定语从句", "category": "语法", "difficulty": 0.6},

    # 阅读类
    {"id": "reading_skimming", "name": "略读技巧", "category": "阅读", "difficulty": 0.4},
    {"id": "reading_scanning", "name": "扫读技巧", "category": "阅读", "difficulty": 0.4},
    {"id": "reading_inference", "name": "推理判断", "category": "阅读", "difficulty": 0.6},
    {"id": "reading_main_idea", "name": "主旨大意", "category": "阅读", "difficulty": 0.5},

    # 写作类
    {"id": "writing_paragraph", "name": "段落写作", "category": "写作", "difficulty": 0.5},
    {"id": "writing_essay", "name": "议论文写作", "category": "写作", "difficulty": 0.7},
    {"id": "writing_email", "name": "邮件写作", "category": "写作", "difficulty": 0.4},
    {"id": "writing_summary", "name": "摘要写作", "category": "写作", "difficulty": 0.6},

    # 听力类
    {"id": "listening_gist", "name": "听力主旨", "category": "听力", "difficulty": 0.4},
    {"id": "listening_detail", "name": "听力细节", "category": "听力", "difficulty": 0.5},
    {"id": "listening_note", "name": "听力笔记", "category": "听力", "difficulty": 0.6},
    {"id": "listening_predict", "name": "听力预测", "category": "听力", "difficulty": 0.5},
]


async def create_tables():
    """创建所有数据库表。"""
    print("Creating database tables...")
    await init_db()
    print("Tables created successfully!")


async def insert_initial_data():
    """插入初始英语学习知识点。"""
    print("Inserting initial knowledge points...")

    async with async_session() as session:
        # 检查是否已有数据
        from sqlalchemy import select, func
        from models.database import KnowledgeState

        result = await session.execute(select(func.count()).select_from(KnowledgeState))
        count = result.scalar()

        if count > 0:
            print(f"Database already has {count} knowledge points, skipping insertion.")
            return

        # 创建一个默认学习者
        default_learner = Learner(
            learner_id="system",
            name="System Learner",
            email="system@eduagent.local",
        )
        session.add(default_learner)

        # 为每个知识点创建默认状态（供系统使用）
        for kp in INITIAL_KNOWLEDGE_POINTS:
            state = KnowledgeState(
                learner_id="system",
                knowledge_id=kp["id"],
                mastery=0.1,
                alpha=1.0,
                beta=9.0,
            )
            session.add(state)

        await session.commit()
        print(f"Inserted {len(INITIAL_KNOWLEDGE_POINTS)} knowledge points.")


async def main():
    """主函数。"""
    try:
        await create_tables()
        await insert_initial_data()
        print("\nDatabase initialization completed!")
        print("\nKnowledge points by category:")

        categories = {}
        for kp in INITIAL_KNOWLEDGE_POINTS:
            cat = kp["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(kp["name"])

        for cat, points in categories.items():
            print(f"  {cat}: {', '.join(points)}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
