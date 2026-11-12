import logging


def wrap_errors(method):
    async def wrapper(*args, **kwargs):
        try:
            return await method(*args, **kwargs)
        except TypeError as e:
            logging.error("TypeError in %s: %s", method.__name__, str(e), exc_info=True)
            raise ValueError(f"Invalid model field or argument: {e}")
        except Exception as e:
            logging.error("Unhandled error in %s", method.__name__, exc_info=True)
            raise ValueError("Something went wrong while processing transaction") from e

    return wrapper
