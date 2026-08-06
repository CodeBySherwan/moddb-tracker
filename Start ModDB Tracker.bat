@echo off
rem Launch the ModDB Tracker GUI with pythonw (no console window).
rem Double-click this file instead of running `python gui.py` in a terminal.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0gui.py" --config "%~dp0config.json"
