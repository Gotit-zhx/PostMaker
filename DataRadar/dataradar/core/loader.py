# coding=utf-8
"""
配置加载模块

负责从 YAML 配置文件和环境变量加载配置。
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

import yaml

from dataradar.utils.time import DEFAULT_TIMEZONE
from dataradar.workspace import ensure_workspace_config, workspace_config_path, workspace_id

logger = logging.getLogger(__name__)


def _get_env_bool(key: str) -> Optional[bool]:
    """从环境变量获取布尔值，如果未设置返回 None"""
    value = os.environ.get(key, "").strip().lower()
    if not value:
        return None
    return value in ("true", "1")


def _get_env_int(key: str, default: int = 0) -> int:
    """从环境变量获取整数值"""
    value = os.environ.get(key, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_int_or_none(key: str) -> Optional[int]:
    """从环境变量获取整数值，未设置时返回 None"""
    value = os.environ.get(key, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _get_env_str(key: str, default: str = "") -> str:
    """从环境变量获取字符串值"""
    return os.environ.get(key, "").strip() or default


def _load_app_config(config_data: Dict) -> Dict:
    """加载应用配置"""
    app_config = config_data.get("app", {})
    advanced = config_data.get("advanced", {})
    return {
        "TIMEZONE": _get_env_str("TIMEZONE") or app_config.get("timezone", DEFAULT_TIMEZONE),
        "DEBUG": _get_env_bool("DEBUG") if _get_env_bool("DEBUG") is not None else advanced.get("debug", False),
    }


def _load_report_config(config_data: Dict) -> Dict:
    """加载报告配置"""
    report_config = config_data.get("report", {})

    sort_by_position_env = _get_env_bool("SORT_BY_POSITION_FIRST")
    max_news_env = _get_env_int("MAX_NEWS_PER_KEYWORD")

    return {
        "REPORT_MODE": report_config.get("mode", "daily"),
        "DISPLAY_MODE": report_config.get("display_mode", "keyword"),
        "RANK_THRESHOLD": report_config.get("rank_threshold", 10),
        "SORT_BY_POSITION_FIRST": sort_by_position_env if sort_by_position_env is not None else report_config.get("sort_by_position_first", False),
        "MAX_NEWS_PER_KEYWORD": max_news_env or report_config.get("max_news_per_keyword", 0),
    }


def _load_weight_config(config_data: Dict) -> Dict:
    """加载权重配置"""
    advanced = config_data.get("advanced", {})
    weight = advanced.get("weight", {})
    return {
        "RANK_WEIGHT": weight.get("rank", 0.6),
        "FREQUENCY_WEIGHT": weight.get("frequency", 0.3),
        "HOTNESS_WEIGHT": weight.get("hotness", 0.1),
    }


def _load_rss_config(config_data: Dict) -> Dict:
    """加载 RSS 配置"""
    rss = config_data.get("rss", {})
    advanced = config_data.get("advanced", {})
    advanced_rss = advanced.get("rss", {})
    advanced_crawler = advanced.get("crawler", {})

    rss_proxy_url = advanced_rss.get("proxy_url", "") or advanced_crawler.get("default_proxy", "")

    freshness_filter = rss.get("freshness_filter", {})

    raw_max_age = freshness_filter.get("max_age_days", 3)
    try:
        max_age_days = int(raw_max_age)
        if max_age_days < 0:
            logger.warning("RSS freshness_filter.max_age_days 为负数 (%d)，使用默认值 3", max_age_days)
            max_age_days = 3
    except (ValueError, TypeError):
        logger.warning("RSS freshness_filter.max_age_days 格式错误 (%s)，使用默认值 3", raw_max_age)
        max_age_days = 3

    return {
        "ENABLED": rss.get("enabled", False),
        "REQUEST_INTERVAL": advanced_rss.get("request_interval", 2000),
        "TIMEOUT": advanced_rss.get("timeout", 15),
        "USE_PROXY": advanced_rss.get("use_proxy", False),
        "PROXY_URL": rss_proxy_url,
        "FEEDS": rss.get("feeds", []),
        "FRESHNESS_FILTER": {
            "ENABLED": freshness_filter.get("enabled", True),
            "MAX_AGE_DAYS": max_age_days,
        },
    }


def _load_ai_config(config_data: Dict) -> Dict:
    """加载 AI 模型配置（LiteLLM 格式）"""
    ai_config = config_data.get("ai", {})

    timeout_env = _get_env_int_or_none("AI_TIMEOUT")

    return {
        "MODEL": _get_env_str("AI_MODEL") or ai_config.get("model", ""),
        "API_KEY": _get_env_str("AI_API_KEY") or ai_config.get("api_key", ""),
        "API_BASE": _get_env_str("AI_API_BASE") or ai_config.get("api_base", ""),
        "TIMEOUT": timeout_env if timeout_env is not None else ai_config.get("timeout", 120),
        "TEMPERATURE": ai_config.get("temperature", 1.0),
        "MAX_TOKENS": ai_config.get("max_tokens", 5000),
        "NUM_RETRIES": ai_config.get("num_retries", 2),
        "FALLBACK_MODELS": ai_config.get("fallback_models", []),
        "EXTRA_PARAMS": ai_config.get("extra_params", {}),
    }


def _load_ai_filter_config(config_data: Dict) -> Dict:
    """加载 AI 智能筛选配置"""
    ai_filter = config_data.get("ai_filter", {})

    return {
        "BATCH_SIZE": ai_filter.get("batch_size", 200),
        "BATCH_INTERVAL": ai_filter.get("batch_interval", 5),
        "INTERESTS_FILE": ai_filter.get("interests_file"),
        "PROMPT_FILE": ai_filter.get("prompt_file", "prompt.txt"),
        "EXTRACT_PROMPT_FILE": ai_filter.get("extract_prompt_file", "extract_prompt.txt"),
        "UPDATE_TAGS_PROMPT_FILE": ai_filter.get("update_tags_prompt_file", "update_tags_prompt.txt"),
        "RECLASSIFY_THRESHOLD": ai_filter.get("reclassify_threshold", 0.6),
        "MIN_SCORE": float(ai_filter.get("min_score", 0)),
    }


def _load_filter_config(config_data: Dict) -> Dict:
    """加载筛选策略配置"""
    filter_cfg = config_data.get("filter", {})

    env_ai_filter = _get_env_bool("AI_FILTER_ENABLED")

    method = filter_cfg.get("method", "keyword")
    if env_ai_filter is True:
        method = "ai"

    if method == "keyword" and not filter_cfg.get("method"):
        ai_filter = config_data.get("ai_filter", {})
        if ai_filter.get("enabled", False):
            method = "ai"

    return {
        "METHOD": method,
        "PRIORITY_SORT_ENABLED": filter_cfg.get("priority_sort_enabled", False),
    }


def _load_storage_config(config_data: Dict) -> Dict:
    """加载存储配置"""
    storage = config_data.get("storage", {})
    formats = storage.get("formats", {})
    local = storage.get("local", {})
    remote = storage.get("remote", {})
    pull = storage.get("pull", {})

    txt_enabled_env = _get_env_bool("STORAGE_TXT_ENABLED")
    html_enabled_env = _get_env_bool("STORAGE_HTML_ENABLED")
    pull_enabled_env = _get_env_bool("PULL_ENABLED")

    return {
        "BACKEND": _get_env_str("STORAGE_BACKEND") or storage.get("backend", "auto"),
        "FORMATS": {
            "SQLITE": formats.get("sqlite", True),
            "TXT": txt_enabled_env if txt_enabled_env is not None else formats.get("txt", True),
            "HTML": html_enabled_env if html_enabled_env is not None else formats.get("html", True),
        },
        "LOCAL": {
            "DATA_DIR": local.get("data_dir", "output"),
            "RETENTION_DAYS": _get_env_int("LOCAL_RETENTION_DAYS") or local.get("retention_days", 0),
        },
        "REMOTE": {
            "ENDPOINT_URL": _get_env_str("S3_ENDPOINT_URL") or remote.get("endpoint_url", ""),
            "BUCKET_NAME": _get_env_str("S3_BUCKET_NAME") or remote.get("bucket_name", ""),
            "ACCESS_KEY_ID": _get_env_str("S3_ACCESS_KEY_ID") or remote.get("access_key_id", ""),
            "SECRET_ACCESS_KEY": _get_env_str("S3_SECRET_ACCESS_KEY") or remote.get("secret_access_key", ""),
            "REGION": _get_env_str("S3_REGION") or remote.get("region", ""),
            "RETENTION_DAYS": _get_env_int("REMOTE_RETENTION_DAYS") or remote.get("retention_days", 0),
        },
        "PULL": {
            "ENABLED": pull_enabled_env if pull_enabled_env is not None else pull.get("enabled", False),
            "DAYS": _get_env_int("PULL_DAYS") or pull.get("days", 7),
        },
    }


def _load_knowledge_base_config(config_data: Dict) -> Dict:
    """加载知识库配置"""
    kb = config_data.get("knowledge_base", {})
    embedding = kb.get("embedding", {})
    enricher = kb.get("enricher", {})
    summarizer = kb.get("summarizer", {})

    return {
        "ENABLED": kb.get("enabled", False),
        "POSTGRES_DSN": _get_env_str("POSTGRES_DSN") or kb.get("postgres_dsn", ""),
        "REDIS_URL": _get_env_str("REDIS_URL") or kb.get("redis_url", ""),
        "EMBEDDING": {
            "ENABLED": embedding.get("enabled", False),
            "MODEL": embedding.get("model", "text-embedding-3-small"),
            "BATCH_SIZE": embedding.get("batch_size", 50),
            "DIMENSIONS": embedding.get("dimensions", 1536),
        },
        "ENRICHER": {
            "ENABLED": enricher.get("enabled", False),
            "USE_PLAYWRIGHT": enricher.get("use_playwright", True),
            "JINA_API_KEY": _get_env_str("JINA_API_KEY") or enricher.get("jina_api_key", ""),
            "RATE_LIMIT_PER_MIN": enricher.get("rate_limit_per_min", 10),
        },
        "SUMMARIZER": {
            "ENABLED": summarizer.get("enabled", False),
            "MAX_TOKENS": summarizer.get("max_tokens", 250),
            "BATCH_SIZE": summarizer.get("batch_size", 20),
            "SKIP_IF_EXISTS": summarizer.get("skip_if_exists", True),
        },
    }


def _load_web_scraper_config(config_data: Dict) -> Dict:
    """加载 Playwright 网页采集配置"""
    ws = config_data.get("web_scraper", {})

    return {
        "ENABLED": ws.get("enabled", False),
        "TIMEOUT": ws.get("timeout", 30000),
        "MIN_DOMAIN_INTERVAL": ws.get("min_domain_interval", 10.0),
        "PROXY_URL": ws.get("proxy_url", ""),
        "TARGETS": ws.get("targets", []),
    }


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径，默认从环境变量 CONFIG_PATH 获取或使用 config/config.yaml

    Returns:
        包含所有配置的字典

    Raises:
        FileNotFoundError: 配置文件不存在
    """
    if config_path is None:
        if workspace_id() != "default":
            config_path = str(ensure_workspace_config())
        else:
            config_path = os.environ.get("CONFIG_PATH") or "config/config.yaml"

    path = Path(config_path)
    if not path.exists():
        # Support running from the repository root and fresh checkouts where
        # only the example configuration exists.
        module_root = Path(__file__).resolve().parents[2]
        candidates = [
            module_root / config_path,
            module_root / "config" / "config.yaml",
            module_root / "config" / "config.example.yaml",
        ]
        path = next((candidate for candidate in candidates if candidate.exists()), path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件 {config_path} 不存在，且未找到 config.example.yaml")

    with open(path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    logger.debug("配置文件加载成功: %s", config_path)

    config = {}

    config.update(_load_app_config(config_data))
    config.update(_load_report_config(config_data))
    config["WEIGHT_CONFIG"] = _load_weight_config(config_data)
    config["RSS"] = _load_rss_config(config_data)
    config["AI"] = _load_ai_config(config_data)
    config["AI_FILTER"] = _load_ai_filter_config(config_data)
    config["FILTER"] = _load_filter_config(config_data)
    config["STORAGE"] = _load_storage_config(config_data)
    config["KNOWLEDGE_BASE"] = _load_knowledge_base_config(config_data)
    config["WEB_SCRAPER"] = _load_web_scraper_config(config_data)

    return config
