import operator
from typing import Any, Optional, Sequence, Dict

from sqlalchemy import and_, or_, not_, desc, asc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db_domains import Base
from db_domains.db import DBSession

DataObject = dict[str, Any]
OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda f, v: f.in_(v),
    "not_in": lambda f, v: ~f.in_(v),
    "like": lambda f, v: f.like(v),
    "ilike": lambda f, v: f.ilike(v),
    "not": lambda f, v: not_(f == v),
}


class DBInterface:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model

    def build_filter_expression(self, filter_def: Dict[str, Any]):
        if "AND" in filter_def:
            return and_(*[self.build_filter_expression(f) for f in filter_def["AND"]])
        elif "OR" in filter_def:
            return or_(*[self.build_filter_expression(f) for f in filter_def["OR"]])
        elif "NOT" in filter_def:
            return not_(self.build_filter_expression(filter_def["NOT"]))
        elif "field" in filter_def:
            field = getattr(self.db_class, filter_def["field"], None)
            op = filter_def.get("op", "==")
            value = filter_def.get("value")
            if field is None:
                raise ValueError(f"Field '{filter_def['field']}' not found in model {self.db_class.__name__}")
            if op not in OPERATORS:
                raise ValueError(f"Unsupported operator: {op}")
            return OPERATORS[op](field, value)
        else:
            raise ValueError(f"Invalid filter structure: {filter_def}")

    def read_all(self) -> Optional[list[Base]]:
        session: Session = DBSession()
        try:
            items = session.query(self.db_class).all()
            return items or None
        except SQLAlchemyError as e:
            session.rollback()
            raise Exception(f"Error reading all records from {self.db_class.__name__}: {str(e)}")
        finally:
            session.close()

    def exists_by_id(self, _id: Any) -> bool:
        session: Session = DBSession()
        try:
            return session.query(self.db_class).filter(self.db_class.id == _id).first() is not None
        except SQLAlchemyError as e:
            session.rollback()
            raise Exception(f"Error checking existence of {self.db_class.__name__} with ID {_id}: {str(e)}")
        finally:
            session.close()

    def read_by_id(self, _id: Any) -> Optional[Base]:
        session: Session = DBSession()
        try:
            return session.get(self.db_class, _id)
        except SQLAlchemyError as e:
            session.rollback()
            raise Exception(f"Error reading {self.db_class.__name__} with ID {_id}: {str(e)}")
        finally:
            session.close()

    def read_by_fields(self, fields: list) -> Optional[Sequence[Base]]:
        session = DBSession()
        try:
            items = session.query(self.db_class).filter(*fields).all()
            return items if items else None
        except Exception as e:
            session.rollback()
            raise Exception(f"Error reading records by fields in {self.db_class.__name__}: {str(e)}")
        finally:
            session.close()

    def read_single_by_fields(self, fields: list) -> Optional[Base]:
        session = DBSession()
        try:
            item = session.query(self.db_class).filter(*fields).first()
            return item if item else None
        except Exception as e:
            session.rollback()
            raise Exception(f"Error reading single record by fields in {self.db_class.__name__}: {str(e)}")
        finally:
            session.close()

    def read_all_by_filters(
            self, filter_expr: Optional[Any] = None, order_by: Optional[Any] = None, limit: int = 10, offset: int = 0,
            order_direction: str = "asc"
    ):
        session: Session = DBSession()
        try:
            query = session.query(self.db_class)

            if filter_expr is not None:
                query = query.filter(filter_expr)

            if order_by is not None:
                if order_direction == "desc":
                    query = query.order_by(desc(order_by))
                else:
                    query = query.order_by(asc(order_by))

            query = query.offset(offset).limit(limit)

            results = query.all()
            return results
        except Exception as e:
            session.close()
            raise Exception(f"Error reading with filters in {self.db_class.__name__}: {str(e)}")
        finally:
            session.close()

    def create(self, data: dict[str, Any]) -> Base:
        session: Session = DBSession()
        try:
            item = self.db_class(**data)
            session.add(item)
            session.commit()
            session.refresh(item)
            return item
        except SQLAlchemyError as e:
            session.rollback()
            raise Exception(f"Error creating {self.db_class.__name__}: {str(e)}")
        finally:
            session.close()

    def update(self, _id: str, data: DataObject, lookup_field: str = None, update_all: bool = False) -> Base | list[
        Base] | None:
        session = DBSession()
        try:
            # Case 1: Lookup by primary key (default behavior)
            if lookup_field is None:
                item: Base = session.get(self.db_class, _id)
                if not item:
                    raise Exception(f"{self.db_class.__name__} with id = {_id} not found")

                for key, value in data.items():
                    setattr(item, key, value)

                session.commit()
                session.refresh(item)
                return item

            # Case 2: Lookup by custom field
            field_attr = getattr(self.db_class, lookup_field, None)
            if field_attr is None:
                raise Exception(f"Field '{lookup_field}' not found in model {self.db_class.__name__}")

            query = session.query(self.db_class).filter(field_attr == _id)

            if update_all:
                items: list[Base] = query.all()
                if not items:
                    raise Exception(f"No records found for {lookup_field} = {_id}")

                for item in items:
                    for key, value in data.items():
                        setattr(item, key, value)

                session.commit()
                for item in items:
                    session.refresh(item)

                return items
            else:
                item: Base = query.first()
                if not item:
                    raise Exception(f"{self.db_class.__name__} with {lookup_field} = {_id} not found")

                for key, value in data.items():
                    setattr(item, key, value)

                session.commit()
                session.refresh(item)
                return item

        except Exception as e:
            session.rollback()
            raise Exception(
                f"Error updating {self.db_class.__name__} with {lookup_field or 'id'} = {_id}: {str(e)}"
            )
        finally:
            session.close()

    def delete(self, filters: list) -> bool | Exception | None:
        session = DBSession()
        try:
            item = session.query(self.db_class).filter(*filters)
            if item:
                session.delete(item)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise Exception(f"Error deleting record from {self.db_class.__name__}: {str(e)}")
        finally:
            session.close()
