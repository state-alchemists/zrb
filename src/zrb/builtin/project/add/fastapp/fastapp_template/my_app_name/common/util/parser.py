import re
from typing import Callable

from sqlalchemy import asc, desc
from sqlalchemy.sql import ClauseElement, ColumnElement
from sqlmodel import SQLModel


def create_default_sort_param_parser() -> (
    Callable[[SQLModel, str], list[ColumnElement]]
):
    def parse_sort_param(model: SQLModel, query: str) -> list[ColumnElement]:
        """
        Parse the sort parameter and return a list of SQLAlchemy ColumnElement objects.

        Args:
            model (Type[SQLModel]): The SQLModel class to be queried.
            query (str): A comma-separated string of fields to sort by.
                        Prefix a field with '-' for descending order.

        Returns:
            list[ColumnElement]: A list of SQLAlchemy ColumnElement objects representing the sort order.

        Example:
            parse_sort_param(UserModel, "name,-age")
            # Returns [asc(UserModel.name), desc(UserModel.age)]
        """
        sorts: list[ColumnElement] = []
        sort_parts = query.split(",")
        for part in sort_parts:
            if part.startswith("-"):
                key = part[1:]
                order = desc
            else:
                key = part
                order = asc
            if hasattr(model, key):
                sorts.append(order(getattr(model, key)))
        return sorts

    return parse_sort_param


def create_default_filter_param_parser() -> (
    Callable[[SQLModel, str], list[ClauseElement]]
):
    def parse_filter_param(model: SQLModel, query: str) -> list[ClauseElement]:
        r"""
        Parse the filter parameter and return a list of SQLAlchemy ClauseElement objects.

        Args:
            model (Type[SQLModel]): The SQLModel class to be queried.
            query (str): A comma-separated string of filters.
                        Each filter should be in the format "field:operator:value".
                        Use '\,' to escape commas within values.

        Returns:
            list[ClauseElement]: A list of SQLAlchemy ClauseElement objects representing the filters.

        Supported operators:
            eq: Equal to
            ne: Not equal to
            gt: Greater than
            gte: Greater than or equal to
            lt: Less than
            lte: Less than or equal to
            like: SQL LIKE (use % for wildcards)
            in: In a list of values (semicolon-separated)

        Example:
            parse_filter_param(UserModel, "age:gte:18,name:like:John%,role:in:admin;user,address:eq:123\, Main St.")
            # Returns [UserModel.age >= 18, UserModel.name.like("John%"), UserModel.role.in_(["admin", "user"]), UserModel.address == "123, Main St."]
        """
        filters: list[ClauseElement] = []
        filter_parts = split_unescaped(query)
        for part in filter_parts:
            match = re.match(r"(.+):(.+):(.+)", part)
            if match:
                key, op, value = match.groups()
                value = value.replace(r"\,", ",")  # Unescape commas in the value
                if hasattr(model, key):
                    column = getattr(model, key)
                    if op == "eq":
                        filters.append(column == value)
                    elif op == "ne":
                        filters.append(column != value)
                    elif op == "gt":
                        filters.append(column > value)
                    elif op == "gte":
                        filters.append(column >= value)
                    elif op == "lt":
                        filters.append(column < value)
                    elif op == "lte":
                        filters.append(column <= value)
                    elif op == "like":
                        filters.append(column.like(value))
                    elif op == "in":
                        filters.append(column.in_(value.split(";")))
        return filters

    return parse_filter_param


def split_unescaped(s: str, delimiter: str = ",") -> list[str]:
    return re.split(r"(?<!\\)" + re.escape(delimiter), s)
