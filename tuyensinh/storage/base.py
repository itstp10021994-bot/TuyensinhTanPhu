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

    def lan_doi_cuoi(self, list_names: list[str]) -> dict | None:
        """Thời điểm (datetime UTC) có thay đổi / xóa dòng gần nhất của từng list — để app biết
        list nào vừa bị sửa thẳng trên SharePoint mà tải lại. None: kho không hỗ trợ."""
        return None
