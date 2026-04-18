"""postmaker personas 命令"""

from postmaker.core.config import get_persona_dir, load_config
from postmaker.persona.loader import load_all_personas


async def cmd_personas(args):
    cfg = load_config()
    personas = load_all_personas(get_persona_dir(cfg))

    if not personas:
        print("未找到人设文件。")
        return

    print(f"共 {len(personas)} 个人设：\n")
    for p in personas:
        topics = ", ".join(p.interests.topics) if p.interests.topics else "全部"
        print(f"  {p.id}")
        print(f"    名称: {p.name}")
        print(f"    描述: {p.description}")
        print(f"    风格: {p.style.tone} / {p.style.language} / {p.style.length_preference}")
        print(f"    关注: {topics} (importance >= {p.interests.min_importance})")
        print()
