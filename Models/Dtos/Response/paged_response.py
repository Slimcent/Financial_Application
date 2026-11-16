from typing import Generic, List, TypeVar

from pydantic import ConfigDict

from Models.Dtos.Response.base_response import BaseResponse

T = TypeVar('T')


class PagedResponse(BaseResponse, Generic[T]):
    """One page of items and the total number of items across all pages.

    ``PagedResponse[SomeResponse](...)`` validates the items as SomeResponse. Without a type argument (as the
    repository returns it, with entities as items) the items are kept as they are; a type argument that is not a
    pydantic type (e.g. an entity class) is checked with isinstance.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_count: int
    page: int
    page_size: int
    items: List[T]
