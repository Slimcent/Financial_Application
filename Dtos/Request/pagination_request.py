from typing import Optional


class PaginationRequest:
    def __init__(
        self,
        page: int = 1,
        page_size: int = 10,
        search_term: Optional[str] = None,
    ):
        self.page = page
        self.page_size = page_size
        self.search_term = search_term
