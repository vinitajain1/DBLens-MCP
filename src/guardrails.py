import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


DEFAULT_LIMIT = 100

UNSAFE_EXPRESSIONS = (
    exp.Alter,
    exp.Attach,
    exp.Command,
    exp.Commit,
    exp.Create,
    exp.Delete,
    exp.Detach,
    exp.Drop,
    exp.Grant,
    exp.Insert,
    exp.Rollback,
    exp.Transaction,
    exp.TruncateTable,
    exp.Update,
)


class UnsafeQueryError(ValueError):
    pass


def prepare_read_query(sql: str, limit: int = DEFAULT_LIMIT) -> str:
    if not sql or not sql.strip():
        raise UnsafeQueryError("SQL query is required")

    try:
        expressions = sqlglot.parse(sql, read="sqlite")
    except ParseError as exc:
        raise UnsafeQueryError(f"SQL parse failed: {exc}") from exc

    if len(expressions) != 1:
        raise UnsafeQueryError("Only one SQL statement is allowed")

    expression = expressions[0]
    if not isinstance(expression, exp.Query):
        raise UnsafeQueryError("Only SELECT-style read queries are allowed")

    for node in expression.walk():
        if isinstance(node, UNSAFE_EXPRESSIONS):
            raise UnsafeQueryError(f"Unsafe SQL expression rejected: {type(node).__name__}")

    if expression.args.get("limit") is None:
        expression = expression.limit(limit)

    return expression.sql(dialect="sqlite")
