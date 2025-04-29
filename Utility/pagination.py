from typing import Generic, List, TypeVar
from Dtos.Response.paged_response import PagedResponse

T = TypeVar("T")


class Pagination:
    @staticmethod
    def paginate(page: int, page_size: int, items: List[T]) -> PagedResponse[T]:
        total_count = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = items[start:end]
        return PagedResponse(total_count, page, page_size, paginated_items)
