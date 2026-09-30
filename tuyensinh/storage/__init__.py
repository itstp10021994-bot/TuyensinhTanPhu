from __future__ import annotations

from .. import config
from .base import Storage


def create_storage() -> Storage:
    """Tạo kho dữ liệu theo BACKEND = "powerautomate" | "sharepoint" | "local"."""
    if config.backend() == "powerautomate":
        from .powerautomate import PowerAutomateStorage

        return PowerAutomateStorage.from_config()
    if config.backend() == "sharepoint":
        from .sharepoint import SharePointStorage

        return SharePointStorage.from_config()
    from .local import LocalStorage

    return LocalStorage(config.get("LOCAL_DB", "data_local.sqlite3"))


__all__ = ["Storage", "create_storage"]
