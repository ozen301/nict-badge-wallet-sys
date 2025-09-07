from nictbw.db.engine import make_engine
from nictbw.models import Base  # imports all model modules via __init__ side-effects
from sqlalchemy import inspect


def main():
    """Initialize the database schema and print created tables."""
    engine = make_engine()
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    print("Created tables:", ", ".join(insp.get_table_names()))


if __name__ == "__main__":
    main()
