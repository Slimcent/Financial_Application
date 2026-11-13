import pytest

from Models.Dtos.Request.pagination_request import PaginationRequest


def test_defaults_are_preserved():
    request = PaginationRequest()

    assert (request.page, request.page_size, request.search_term) == (1, 10, None)


@pytest.mark.parametrize("page", [1, 2, 1_000])
def test_valid_page_is_accepted(page):
    assert PaginationRequest(page=page).page == page


@pytest.mark.parametrize("page_size", [1, 10, 50], ids=["minimum", "default", "maximum"])
def test_valid_page_size_is_accepted(page_size):
    assert PaginationRequest(page_size=page_size).page_size == page_size


def test_invalid_page_is_rejected(invalid_page, assert_rejected):
    assert_rejected(PaginationRequest, {"page": invalid_page}, "page")


def test_invalid_page_size_is_rejected(invalid_page_size, assert_rejected):
    assert_rejected(PaginationRequest, {"page_size": invalid_page_size}, "page_size")


def test_page_size_above_fifty_is_rejected(assert_rejected):
    assert_rejected(PaginationRequest, {"page_size": 51}, "page_size", "less_than_equal")


@pytest.mark.parametrize("raw, expected", [
    (None, None),
    ("Doe", "Doe"),
    ("  example@example.com ", "example@example.com"),
    ("x" * 255, "x" * 255),
], ids=["none", "text", "trimmed", "max-length"])
def test_valid_search_term_is_accepted(raw, expected):
    assert PaginationRequest(search_term=raw).search_term == expected


def test_blank_search_term_becomes_none(blank_value):
    assert PaginationRequest(search_term=blank_value).search_term is None


@pytest.mark.parametrize("value", ["x" * 256, 5], ids=["too-long", "int"])
def test_invalid_search_term_is_rejected(value, assert_rejected):
    assert_rejected(PaginationRequest, {"search_term": value}, "search_term")
