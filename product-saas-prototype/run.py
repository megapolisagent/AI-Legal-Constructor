"""Точка входа: python run.py, затем открыть http://127.0.0.1:5001 в браузере.
Debug-режим (интерактивная консоль при ошибке) по умолчанию выключен — включить для
разработки: LEGAL_CONSTRUCTOR_DEBUG=1 python run.py"""
from app.main import app, DEBUG

if __name__ == "__main__":
    app.run(debug=DEBUG, port=5001)
