from decimal import Decimal

import pytest

from Dtos.Request.pagination_request import PaginationRequest
from Dtos.Request.transaction_request import (
    FundsTransferRequest,
    TransactionRequest,
    TransactionsRequest,
    UserTransactionsRequest,
)

FILTER_IDENTIFIER_FIELDS = ["sender_id", "account_type_id", "transaction_type_id", "transaction_mode_id",
                            "transaction_status_id"]
FILTER_FIELDS = FILTER_IDENTIFIER_FIELDS + ["account_number"]


class TestTransactionRequest:
    REQUIRED_FIELDS = ["user_id", "account_id", "account_number", "amount", "transaction_type_id",
                       "transaction_mode_id", "transaction_status_id"]
    IDENTIFIER_FIELDS = ["user_id", "account_id", "transaction_type_id", "transaction_mode_id",
                         "transaction_status_id"]

    def test_valid_request_is_accepted_with_optional_fields_unset(self, transaction_payload):
        request = TransactionRequest(**transaction_payload)

        assert request.amount == Decimal("100.00")
        assert (request.sender_id, request.description) == (None, None)

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_missing_required_field_is_rejected(self, transaction_payload, field, omit, assert_rejected):
        assert_rejected(TransactionRequest, omit(transaction_payload, field), field, "missing")

    @pytest.mark.parametrize("field", IDENTIFIER_FIELDS + ["sender_id"])
    def test_valid_identifier_is_accepted(self, transaction_payload, field, valid_identifier):
        assert getattr(TransactionRequest(**{**transaction_payload, field: valid_identifier}), field) == valid_identifier

    @pytest.mark.parametrize("field", IDENTIFIER_FIELDS)
    def test_invalid_identifier_is_rejected(self, transaction_payload, field, invalid_identifier, assert_rejected):
        assert_rejected(TransactionRequest, {**transaction_payload, field: invalid_identifier}, field)

    @pytest.mark.parametrize("value", [0, -1, "1", 1.0, True], ids=["zero", "negative", "string", "float", "bool"])
    def test_invalid_optional_sender_id_is_rejected(self, transaction_payload, value, assert_rejected):
        assert_rejected(TransactionRequest, {**transaction_payload, "sender_id": value}, "sender_id")

    def test_valid_account_number_is_accepted(self, transaction_payload, valid_account_number):
        raw, expected = valid_account_number

        assert TransactionRequest(**{**transaction_payload, "account_number": raw}).account_number == expected

    def test_invalid_account_number_is_rejected(self, transaction_payload, invalid_account_number, assert_rejected):
        assert_rejected(TransactionRequest, {**transaction_payload, "account_number": invalid_account_number},
                        "account_number")

    def test_valid_amount_is_accepted_as_two_place_decimal(self, transaction_payload, valid_amount):
        raw, expected = valid_amount
        amount = TransactionRequest(**{**transaction_payload, "amount": raw}).amount

        assert isinstance(amount, Decimal)
        assert amount == expected
        assert amount.as_tuple().exponent == -2

    def test_invalid_amount_is_rejected(self, transaction_payload, invalid_amount, assert_rejected):
        assert_rejected(TransactionRequest, {**transaction_payload, "amount": invalid_amount}, "amount")

    def test_valid_description_is_accepted(self, transaction_payload, valid_description):
        raw, expected = valid_description

        assert TransactionRequest(**{**transaction_payload, "description": raw}).description == expected

    def test_invalid_description_is_rejected(self, transaction_payload, invalid_description, assert_rejected):
        assert_rejected(TransactionRequest, {**transaction_payload, "description": invalid_description}, "description")


class TestUserTransactionsRequest:
    def test_user_id_is_required(self, assert_rejected):
        assert_rejected(UserTransactionsRequest, {}, "user_id", "missing")

    def test_invalid_user_id_is_rejected(self, invalid_identifier, assert_rejected):
        assert_rejected(UserTransactionsRequest, {"user_id": invalid_identifier}, "user_id")

    def test_filters_are_optional(self, user_transactions_payload):
        request = UserTransactionsRequest(**user_transactions_payload)

        assert all(getattr(request, field) is None for field in FILTER_FIELDS)

    def test_explicit_none_filters_are_accepted(self, user_transactions_payload):
        request = UserTransactionsRequest(**user_transactions_payload, **dict.fromkeys(FILTER_FIELDS))

        assert all(getattr(request, field) is None for field in FILTER_FIELDS)

    @pytest.mark.parametrize("field", FILTER_IDENTIFIER_FIELDS)
    def test_valid_filter_identifier_is_accepted(self, user_transactions_payload, field):
        assert getattr(UserTransactionsRequest(**user_transactions_payload, **{field: 2}), field) == 2

    @pytest.mark.parametrize("field", FILTER_IDENTIFIER_FIELDS)
    @pytest.mark.parametrize("value", [0, -1, "1", True], ids=["zero", "negative", "string", "bool"])
    def test_invalid_filter_identifier_is_rejected(self, user_transactions_payload, field, value, assert_rejected):
        assert_rejected(UserTransactionsRequest, {**user_transactions_payload, field: value}, field)

    def test_valid_account_number_filter_is_accepted(self, user_transactions_payload, valid_account_number):
        raw, expected = valid_account_number

        assert UserTransactionsRequest(**user_transactions_payload, account_number=raw).account_number == expected

    def test_invalid_account_number_filter_is_rejected(self, user_transactions_payload, invalid_account_number_filter,
                                                       assert_rejected):
        assert_rejected(UserTransactionsRequest,
                        {**user_transactions_payload, "account_number": invalid_account_number_filter}, "account_number")


class TestTransactionsRequest:
    def test_no_arguments_gives_pagination_defaults_and_no_filters(self):
        request = TransactionsRequest()

        assert (request.page, request.page_size, request.search_term) == (1, 10, None)
        assert request.user_id is None
        assert all(getattr(request, field) is None for field in FILTER_FIELDS)

    def test_is_a_pagination_request(self):
        assert issubclass(TransactionsRequest, PaginationRequest)

    def test_filters_and_pagination_are_accepted_together(self):
        request = TransactionsRequest(user_id=3, account_type_id=1, transaction_status_id=2,
                                      account_number=" 2606387058 ", page=2, page_size=50, search_term=" Doe ")

        assert (request.user_id, request.account_type_id, request.transaction_status_id) == (3, 1, 2)
        assert (request.account_number, request.page, request.page_size, request.search_term) == (
            "2606387058", 2, 50, "Doe")

    @pytest.mark.parametrize("field", ["user_id"] + FILTER_IDENTIFIER_FIELDS)
    @pytest.mark.parametrize("value", [0, -1, "1", True], ids=["zero", "negative", "string", "bool"])
    def test_invalid_filter_identifier_is_rejected(self, field, value, assert_rejected):
        assert_rejected(TransactionsRequest, {field: value}, field)

    def test_invalid_account_number_filter_is_rejected(self, invalid_account_number_filter, assert_rejected):
        assert_rejected(TransactionsRequest, {"account_number": invalid_account_number_filter}, "account_number")

    def test_invalid_page_is_rejected(self, invalid_page, assert_rejected):
        assert_rejected(TransactionsRequest, {"page": invalid_page}, "page")

    def test_invalid_page_size_is_rejected(self, invalid_page_size, assert_rejected):
        assert_rejected(TransactionsRequest, {"page_size": invalid_page_size}, "page_size")

    def test_blank_search_term_becomes_none(self, blank_value):
        assert TransactionsRequest(search_term=blank_value).search_term is None


class TestFundsTransferRequest:
    REQUIRED_FIELDS = ["amount", "sender_account_number", "receiver_account_number"]
    ACCOUNT_NUMBER_FIELDS = ["sender_account_number", "receiver_account_number"]

    def test_valid_request_is_accepted(self, funds_transfer_payload):
        request = FundsTransferRequest(**funds_transfer_payload, description="Rent")

        assert request.amount == Decimal("300.00")
        assert request.description == "Rent"

    def test_description_is_optional(self, funds_transfer_payload):
        assert FundsTransferRequest(**funds_transfer_payload).description is None

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_missing_required_field_is_rejected(self, funds_transfer_payload, field, omit, assert_rejected):
        assert_rejected(FundsTransferRequest, omit(funds_transfer_payload, field), field, "missing")

    @pytest.mark.parametrize("receiver", ["2606387058", "  2606387058 "], ids=["identical", "identical-after-trim"])
    def test_matching_sender_and_receiver_are_rejected(self, funds_transfer_payload, receiver, assert_rejected):
        error = assert_rejected(FundsTransferRequest, {**funds_transfer_payload, "receiver_account_number": receiver},
                                field=None, error_type="value_error")

        assert "must be different" in str(error)

    @pytest.mark.parametrize("field", ACCOUNT_NUMBER_FIELDS)
    def test_valid_account_number_is_accepted(self, funds_transfer_payload, field, valid_account_number):
        raw, expected = valid_account_number
        other = "sender_account_number" if field == "receiver_account_number" else "receiver_account_number"
        payload = {**funds_transfer_payload, field: raw, other: "1111111111"}

        assert getattr(FundsTransferRequest(**payload), field) == expected

    @pytest.mark.parametrize("field", ACCOUNT_NUMBER_FIELDS)
    def test_invalid_account_number_is_rejected(self, funds_transfer_payload, field, invalid_account_number,
                                                assert_rejected):
        assert_rejected(FundsTransferRequest, {**funds_transfer_payload, field: invalid_account_number}, field)

    def test_valid_amount_is_accepted_as_two_place_decimal(self, funds_transfer_payload, valid_amount):
        raw, expected = valid_amount
        amount = FundsTransferRequest(**{**funds_transfer_payload, "amount": raw}).amount

        assert isinstance(amount, Decimal)
        assert amount == expected
        assert amount.as_tuple().exponent == -2

    def test_invalid_amount_is_rejected(self, funds_transfer_payload, invalid_amount, assert_rejected):
        assert_rejected(FundsTransferRequest, {**funds_transfer_payload, "amount": invalid_amount}, "amount")

    def test_valid_description_is_accepted(self, funds_transfer_payload, valid_description):
        raw, expected = valid_description

        assert FundsTransferRequest(**funds_transfer_payload, description=raw).description == expected

    def test_invalid_description_is_rejected(self, funds_transfer_payload, invalid_description, assert_rejected):
        assert_rejected(FundsTransferRequest, {**funds_transfer_payload, "description": invalid_description},
                        "description")
