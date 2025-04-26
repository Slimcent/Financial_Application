from Dtos.Request.transaction_request import TransactionRequest


class TransactionRequestValidator:
    @staticmethod
    def validate(transaction_request: 'TransactionRequest'):
        if transaction_request.amount <= 0:
            raise ValueError("Amount must be greater than zero")

        if not transaction_request.account_number:
            raise ValueError("Account number is required")

        if transaction_request.transaction_type_id not in [1, 2, 3]:
            raise ValueError("Invalid transaction type")

        if transaction_request.transaction_mode_id not in [1, 2]:
            raise ValueError("Invalid transaction mode")

        if transaction_request.transaction_status_id not in [1, 2]:
            raise ValueError("Invalid transaction status")
