"""Точка входа: python run.py, затем открыть http://127.0.0.1:5001 в браузере."""
from app.main import app

if __name__ == "__main__":
    app.run(debug=True, port=5001)
