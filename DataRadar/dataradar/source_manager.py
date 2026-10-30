"""
源管理器 — 管理 config.yaml 中的 RSS 源和 Web 采集目标。

使用 ruamel.yaml 实现保留注释的 YAML 读写。
"""

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from ruamel.yaml import YAML
from dataradar.workspace import ensure_workspace_config, workspace_config_path, workspace_id


class SourceManager:
    """管理 config.yaml 中的 RSS 源和 Web 采集目标。"""

    def __init__(self, config_path: str = None):
        module_root = Path(__file__).resolve().parent.parent
        if config_path is None:
            if workspace_id() != "default":
                self.config_path = ensure_workspace_config()
            else:
                configured_path = os.environ.get("CONFIG_PATH")
                if configured_path:
                    candidate = Path(configured_path)
                    if candidate.is_absolute() or candidate.exists():
                        self.config_path = candidate
                    else:
                        self.config_path = module_root / candidate
                else:
                    self.config_path = module_root / "config" / "config.yaml"
        else:
            candidate = Path(config_path)
            self.config_path = candidate if candidate.is_absolute() else Path.cwd() / candidate

        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._yaml.width = 120

    def _load(self):
        if not self.config_path.exists():
            if workspace_id() != "default":
                self.config_path = ensure_workspace_config()
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return self._yaml.load(f) or {}
            module_example = Path(__file__).resolve().parent.parent / "config" / "config.example.yaml"
            local_example = self.config_path.with_name("config.example.yaml")
            example_path = local_example if local_example.exists() else module_example
            if not example_path.exists():
                raise FileNotFoundError(
                    f"配置文件 {self.config_path} 不存在，且未找到 config.example.yaml"
                )
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(example_path, self.config_path)
        with open(self.config_path, "r", encoding="utf-8") as f:
            return self._yaml.load(f) or {}

    def _save(self, data):
        with open(self.config_path, "w", encoding="utf-8") as f:
            self._yaml.dump(data, f)

    @staticmethod
    def _auto_id(name: str) -> str:
        """从 name 自动生成 kebab-case ID"""
        s = name.lower().strip()
        s = re.sub(r"[^a-z0-9\s-]", "", s)
        s = re.sub(r"[\s_]+", "-", s)
        s = re.sub(r"-+", "-", s).strip("-")
        return s or "custom-feed"

    @staticmethod
    def _rss_feeds(data):
        rss = data.setdefault("rss", {})
        feeds = rss.get("feeds")
        if not isinstance(feeds, list):
            feeds = []
            rss["feeds"] = feeds
        return rss, feeds

    # ── RSS 源管理 ──────────────────────────────────────────────

    def list_feeds(self) -> List[Dict]:
        """列出所有 RSS 源及其状态"""
        data = self._load()
        _, feeds = self._rss_feeds(data)

        result = []
        for feed in feeds:
            result.append({
                "id": feed.get("id", ""),
                "name": feed.get("name", ""),
                "url": feed.get("url", ""),
                "enabled": feed.get("enabled", True),
                "max_age_days": feed.get("max_age_days", 3),
                "content_type": feed.get("content_type", "text"),
            })
        return result

    def add_feed(
        self,
        url: str,
        id: Optional[str] = None,
        name: str = "",
        max_age_days: int = 3,
        enabled: bool = True,
        content_type: str = "text",
    ) -> Dict:
        """添加新 RSS 源到 config.yaml"""
        data = self._load()
        rss, feeds = self._rss_feeds(data)

        if not name:
            name = url.split("//")[-1].split("/")[0]

        if not id:
            id = self._auto_id(name)

        existing_ids = {f.get("id") for f in feeds}
        if id in existing_ids:
            raise ValueError(f"RSS 源 ID 已存在: {id}")

        new_feed = {
            "id": id,
            "name": name,
            "url": url,
            "max_age_days": max_age_days,
        }
        if not enabled:
            new_feed["enabled"] = False
        if content_type != "text":
            new_feed["content_type"] = content_type

        feeds.append(new_feed)
        self._save(data)

        return {"id": id, "name": name, "url": url, "status": "added"}

    def remove_feed(self, feed_id: str) -> bool:
        """从 config.yaml 删除 RSS 源"""
        data = self._load()
        rss, feeds = self._rss_feeds(data)

        original_len = len(feeds)
        rss["feeds"] = [f for f in feeds if f.get("id") != feed_id]

        if len(rss["feeds"]) == original_len:
            return False

        self._save(data)
        return True

    def enable_feed(self, feed_id: str) -> bool:
        """启用 RSS 源"""
        return self._set_feed_enabled(feed_id, True)

    def disable_feed(self, feed_id: str) -> bool:
        """禁用 RSS 源"""
        return self._set_feed_enabled(feed_id, False)

    def _set_feed_enabled(self, feed_id: str, enabled: bool) -> bool:
        data = self._load()
        _, feeds = self._rss_feeds(data)

        for feed in feeds:
            if feed.get("id") == feed_id:
                if enabled:
                    if "enabled" in feed:
                        del feed["enabled"]
                else:
                    feed["enabled"] = False
                self._save(data)
                return True
        return False

    def test_feed(self, id_or_url: str) -> Dict:
        """测试 RSS 源：实际抓取并返回前 5 条"""
        url = id_or_url
        feed_name = id_or_url
        feed_id = id_or_url

        if not id_or_url.startswith(("http://", "https://")):
            data = self._load()
            _, feeds = self._rss_feeds(data)
            found = None
            for f in feeds:
                if f.get("id") == id_or_url:
                    found = f
                    break
            if not found:
                return {"success": False, "error": f"未找到 RSS 源: {id_or_url}"}
            url = found.get("url", "")
            feed_name = found.get("name", id_or_url)
            feed_id = found.get("id", id_or_url)

        try:
            from dataradar.crawler.rss import RSSFetcher, RSSFeedConfig

            feed_config = RSSFeedConfig(
                id=feed_id if not id_or_url.startswith("http") else "test",
                name=feed_name,
                url=url,
                max_items=5,
                enabled=True,
                max_age_days=0,
            )

            fetcher = RSSFetcher(
                feeds=[feed_config],
                request_interval=0,
                timeout=15,
                use_proxy=False,
                proxy_url="",
                timezone="UTC",
                freshness_enabled=False,
                default_max_age_days=0,
            )

            rss_data = asyncio.run(fetcher.fetch_all())
            if not rss_data:
                return {"success": False, "error": "未获取到任何数据", "url": url}

            items = []
            for fid, feed_items in rss_data.items.items():
                for item in feed_items[:5]:
                    items.append({
                        "title": item.title,
                        "url": item.url,
                        "published_at": item.published_at or "",
                    })

            return {
                "success": True,
                "feed_name": feed_name,
                "url": url,
                "item_count": len(items),
                "items": items[:5],
            }
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    # ── Web 采集目标管理 ──────────────────────────────────────────

    def list_targets(self) -> List[Dict]:
        """列出所有 Web 采集目标"""
        data = self._load()
        ws = data.get("web_scraper", {})
        targets = ws.get("targets", []) or []

        result = []
        for t in targets:
            result.append({
                "id": t.get("id", ""),
                "name": t.get("name", ""),
                "url": t.get("url", ""),
                "enabled": t.get("enabled", True),
                "list_selector": t.get("list_selector", ""),
                "title_selector": t.get("title_selector", ""),
                "link_selector": t.get("link_selector", ""),
                "max_items": t.get("max_items", 30),
            })
        return result

    def add_target(
        self,
        url: str,
        id: Optional[str] = None,
        name: str = "",
        list_selector: str = "",
        title_selector: str = "",
        link_selector: str = "",
        max_items: int = 30,
        enabled: bool = True,
    ) -> Dict:
        """添加新 Web 采集目标"""
        data = self._load()
        ws = data.setdefault("web_scraper", {})
        targets = ws.get("targets", None)
        if targets is None:
            targets = []
            ws["targets"] = targets

        if not name:
            name = url.split("//")[-1].split("/")[0]

        if not id:
            id = self._auto_id(name)

        existing_ids = {t.get("id") for t in targets}
        if id in existing_ids:
            raise ValueError(f"Web 采集目标 ID 已存在: {id}")

        new_target = {
            "id": id,
            "name": name,
            "url": url,
            "max_items": max_items,
        }
        if list_selector:
            new_target["list_selector"] = list_selector
        if title_selector:
            new_target["title_selector"] = title_selector
        if link_selector:
            new_target["link_selector"] = link_selector
        if not enabled:
            new_target["enabled"] = False

        targets.append(new_target)
        self._save(data)

        return {"id": id, "name": name, "url": url, "status": "added"}

    def remove_target(self, target_id: str) -> bool:
        """删除 Web 采集目标"""
        data = self._load()
        ws = data.get("web_scraper", {})
        targets = ws.get("targets", []) or []

        original_len = len(targets)
        ws["targets"] = [t for t in targets if t.get("id") != target_id]

        if len(ws["targets"]) == original_len:
            return False

        self._save(data)
        return True

    def enable_target(self, target_id: str) -> bool:
        return self._set_target_enabled(target_id, True)

    def disable_target(self, target_id: str) -> bool:
        return self._set_target_enabled(target_id, False)

    def _set_target_enabled(self, target_id: str, enabled: bool) -> bool:
        data = self._load()
        ws = data.get("web_scraper", {})
        targets = ws.get("targets", []) or []

        for t in targets:
            if t.get("id") == target_id:
                if enabled:
                    if "enabled" in t:
                        del t["enabled"]
                else:
                    t["enabled"] = False
                self._save(data)
                return True
        return False

    def test_target(self, id_or_url: str) -> Dict:
        """测试 Web 采集目标"""
        url = id_or_url
        target_name = id_or_url
        target_config = None

        if not id_or_url.startswith(("http://", "https://")):
            data = self._load()
            ws = data.get("web_scraper", {})
            targets = ws.get("targets", []) or []
            for t in targets:
                if t.get("id") == id_or_url:
                    target_config = t
                    break
            if not target_config:
                return {"success": False, "error": f"未找到 Web 采集目标: {id_or_url}"}
            url = target_config.get("url", "")
            target_name = target_config.get("name", id_or_url)

        try:
            from dataradar.crawler.web.scraper import PlaywrightScraper

            scraper_cfg = {
                "enabled": True,
                "timeout": 30000,
                "min_domain_interval": 0,
                "targets": [target_config] if target_config else [{
                    "id": "test",
                    "name": target_name,
                    "url": url,
                    "max_items": 5,
                }],
            }

            scraper = PlaywrightScraper(
                scraper_config=scraper_cfg,
                proxy_url="",
                ai_client=None,
            )

            import asyncio
            from datetime import datetime
            crawl_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
            items = asyncio.run(scraper.fetch_all(crawl_time=crawl_time))

            results = []
            for item in items[:5]:
                results.append({
                    "title": item.title,
                    "url": item.url,
                })

            return {
                "success": True,
                "target_name": target_name,
                "url": url,
                "item_count": len(results),
                "items": results,
            }
        except ImportError:
            return {
                "success": False,
                "error": "Playwright 未安装。请执行: pip install playwright playwright-stealth && playwright install chromium",
                "url": url,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    # ── 通用操作 ──────────────────────────────────────────────────

    def remove_source(self, source_id: str) -> bool:
        """删除源（自动识别 RSS 或 Web）"""
        if self.remove_feed(source_id):
            return True
        return self.remove_target(source_id)

    def enable_source(self, source_id: str) -> bool:
        """启用源（自动识别类型）"""
        if self.enable_feed(source_id):
            return True
        return self.enable_target(source_id)

    def disable_source(self, source_id: str) -> bool:
        """禁用源（自动识别类型）"""
        if self.disable_feed(source_id):
            return True
        return self.disable_target(source_id)
