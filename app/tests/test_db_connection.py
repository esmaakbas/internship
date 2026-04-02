from config import SQLALCHEMY_DATABASE_URI
from sqlalchemy import create_engine, text


def test_select_one():
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URI)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            print("SELECT 1 ->", result)
            return 0
    except Exception as e:
        print("ERROR connecting to DB:", repr(e))
        return 2


if __name__ == '__main__':
    raise SystemExit(test_select_one())
