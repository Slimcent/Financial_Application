"""Fixtures shared by unit tests of more than one layer.

Imports happen inside the fixtures, so test packages that do not use them (e.g. the DTO tests) never load
SQLAlchemy or the entities.
"""
import pytest


@pytest.fixture(scope="session")
def metadata_ddl():
    """The DDL statements `Base.metadata.create_all()` would run on a database (by URL, e.g. "mysql://"), trimmed.

    Uses SQLAlchemy's mock engine: the statements are only compiled, nothing is executed and no database
    is contacted. Results are cached per URL.
    """
    from sqlalchemy import create_mock_engine

    from Models.Entities import Base

    cache = {}

    def _metadata_ddl(url):
        if url not in cache:
            statements = []
            engine = create_mock_engine(
                url, lambda sql, *multiparams, **params: statements.append(str(sql.compile(dialect=engine.dialect)).strip())
            )
            Base.metadata.create_all(engine, checkfirst=False)
            cache[url] = statements
        return cache[url]

    return _metadata_ddl
