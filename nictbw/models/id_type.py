from sqlalchemy import BigInteger, Integer

# Use BigInteger by default, with a SQLite-safe Integer variant for autoincrement PKs.
ID_TYPE = BigInteger().with_variant(Integer, "sqlite")
