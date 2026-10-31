import sys
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        # Compatibilidad defensiva para Python 3.14 con Django 5.x template context copy
        if sys.version_info >= (3, 14):
            try:
                import django.template.context

                def _patched_copy(self):
                    dup = self.__class__.__new__(self.__class__)
                    dup.__dict__.update(self.__dict__)
                    dup.dicts = self.dicts[:]
                    return dup

                django.template.context.BaseContext.__copy__ = _patched_copy
            except Exception:
                pass
