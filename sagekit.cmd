@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
python -m sagekit %*
