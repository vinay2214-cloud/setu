"""SQLAlchemy reflection registry for every checked-in schema table.

The SQL schema is the DDL source of truth; reflecting it avoids a second drifting
schema definition while still providing mapped SQLAlchemy classes for all tables.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import registry

from app.db import engine

metadata = MetaData()
mapper_registry = registry(metadata=metadata)
model_classes: dict[str, type] = {}


def initialize_models() -> None:
    metadata.reflect(bind=engine)
    mapped_tables = {mapper.local_table.name for mapper in mapper_registry.mappers}
    for table in metadata.sorted_tables:
        if table.name not in mapped_tables:
            model = type("".join(part.title() for part in table.name.split("_")), (), {})
            mapper_registry.map_imperatively(model, table)
            model_classes[table.name] = model
        else:
            model_classes[table.name] = next(
                mapper.class_
                for mapper in mapper_registry.mappers
                if mapper.local_table.name == table.name
            )


def model_for(table_name: str) -> type:
    model = model_classes.get(table_name)
    if model is None:
        raise KeyError(table_name)
    return model
