@echo off
REM Убедитесь, что используете правильный путь к Python, если он не добавлен в PATH
SET PYTHON_PATH=python

REM Путь к скрипту csfloat_helper.py (он находится в той же директории, что и батник)
SET SCRIPT_PATH=%~dp0csfloat_helper.py

REM Запуск скрипта с использованием Python
"%PYTHON_PATH%" "%SCRIPT_PATH%"

REM Задержка, чтобы консоль оставалась открытой после завершения
pause
