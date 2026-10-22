from django.apps import AppConfig


class CartConfig(AppConfig):
    name = "cart"

    def ready(self):
        from . import signals  # noqa: F401
