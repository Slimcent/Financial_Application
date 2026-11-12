from typing import List, Generic, TypeVar

T = TypeVar('T')


class PagedResponse(Generic[T]):
    def __init__(self, total_count: int, page: int, page_size: int, items: List[T]):
        self.total_count = total_count
        self.page = page
        self.page_size = page_size
        self.items = items

    def __repr__(self):
        lines = ["PagedResponse("]
        lines.append(f"  total_count={self.total_count},")
        lines.append(f"  page={self.page},")
        lines.append(f"  page_size={self.page_size}")
        lines.append("  items=[")
        for item in self.items:
            lines.append(f"    {repr(item)},")
        lines.append("  ],")
        lines.append(")")
        return "\n".join(lines)

