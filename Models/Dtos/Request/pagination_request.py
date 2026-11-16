from typing import Annotated

from pydantic import Field, Strict

from Models.Dtos.Request.base_request import BaseRequest, DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SearchTerm


class PaginationRequest(BaseRequest):
    page: Annotated[int, Strict(), Field(ge=1)] = DEFAULT_PAGE
    page_size: Annotated[int, Strict(), Field(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE
    search_term: SearchTerm = None
