import sys

from django.apps import AppConfig


class TradingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "trading"
    verbose_name = "量化终端"

    def ready(self):
        # 行情模拟器只在 runserver 实际服务的进程里启动:
        # - autoreload 模式:仅子进程(RUN_MAIN=true)启动,父进程跳过
        # - --noreload 模式:直接启动
        # - test / shell / migrate 等场景不启动
        import os

        from django.conf import settings

        if not getattr(settings, "MARKET_SIMULATION_ENABLED", False):
            return
        if "runserver" not in sys.argv:
            return
        if "test" in sys.argv:
            return
        if "--noreload" not in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        from .services.market_sim import start_simulator

        start_simulator()
