from __future__ import annotations

from abc import ABC, abstractmethod


class Storage(ABC):
    """Kho dữ liệu dạng "list + item" giống SharePoint List.

    Mỗi item là dict với khóa "id" (chuỗi) cùng các trường theo schema.
    Ngày được lưu dạng chuỗi ISO "YYYY-MM-DD".
    """

    @abstractmethod
    def list_items(self, list_name: str) -> list[dict]: ...

    @abstractmethod
    def get_item(self, list_name: str, item_id: str) -> dict | None: ...

    @abstractmethod
    def create_item(self, list_name: str, data: dict) -> dict: ...

    @abstractmethod
    def update_item(self, list_name: str, item_id: str, data: dict) -> dict: ...

    @abstractmethod
    def delete_item(self, list_name: str, item_id: str) -> None: ...
