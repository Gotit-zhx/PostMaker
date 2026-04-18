"""postmaker config 命令"""

import json

from postmaker.core.config import load_config


async def cmd_config(args):
    cfg = load_config()

    if args.section:
        section = cfg.get(args.section)
        if section is None:
            print(f"配置段 '{args.section}' 不存在。可用: {', '.join(cfg.keys())}")
            return
        _print_section(args.section, section)
    else:
        for key in cfg:
            _print_section(key, cfg[key])


def _print_section(name: str, data):
    print(f"[{name}]")
    if isinstance(data, dict):
        for k, v in data.items():
            if k in ("api_key",) and v:
                v = v[:8] + "..."
            print(f"  {k}: {v}")
    else:
        print(f"  {data}")
    print()
