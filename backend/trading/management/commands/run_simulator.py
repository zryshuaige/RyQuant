"""
常驻行情模拟器:生产部署(gunicorn/uwsgi 不会自动启动 runserver 的模拟器线程)时,
用本命令常驻循环驱动 market_sim.tick,保持行情与撮合运转。
"""
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from trading.services import market_sim

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "常驻循环驱动行情 tick(生产环境替代 runserver 自动启动的模拟器线程)"

    def handle(self, *args, **options):
        interval = max(getattr(settings, "SIMULATOR_TICK_SECONDS", 3), 1)
        self.stdout.write(f"行情模拟器常驻启动,每 {interval}s tick(Ctrl+C 退出)")
        try:
            while True:
                time.sleep(interval)
                close_old_connections()
                try:
                    market_sim.tick()
                except Exception:
                    logger.exception("行情模拟 tick 失败")
                close_old_connections()
        except KeyboardInterrupt:
            self.stdout.write("行情模拟器已退出")