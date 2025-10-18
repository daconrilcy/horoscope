import os

from backend.core.settings import get_settings
from backend.infra.astro.internal_astro import InternalAstroEngine
from backend.infra.content_repo import JSONContentRepository
from backend.infra.repositories import InMemoryChartRepo, RedisChartRepo


class Container:
    def __init__(self):
        self.settings = get_settings()
        base_dir = os.path.dirname(__file__)
        infra_dir = os.path.normpath(os.path.join(base_dir, "..", "infra"))
        content_path = os.path.join(infra_dir, "content.json")
        self.content_repo = JSONContentRepository(path=content_path)
        self.astro = InternalAstroEngine()
        if self.settings.REDIS_URL:
            try:
                self.chart_repo = RedisChartRepo(self.settings.REDIS_URL)
                self.storage_backend = "redis"
            except Exception as err:
                if getattr(self.settings, "REQUIRE_REDIS", False):
                    raise RuntimeError("Redis required but unavailable") from err
                self.chart_repo = InMemoryChartRepo()
                self.storage_backend = "memory-fallback"
        else:
            if getattr(self.settings, "REQUIRE_REDIS", False):
                raise RuntimeError("Redis required but REDIS_URL not set")
            self.chart_repo = InMemoryChartRepo()
            self.storage_backend = "memory"


container = Container()
