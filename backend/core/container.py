import os

from infra.astro.internal_astro import InternalAstroEngine
from infra.content_repo import JSONContentRepository
from infra.repositories import InMemoryChartRepo, RedisChartRepo

from core.settings import get_settings


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
            except Exception:
                self.chart_repo = InMemoryChartRepo()
        else:
            self.chart_repo = InMemoryChartRepo()


container = Container()
