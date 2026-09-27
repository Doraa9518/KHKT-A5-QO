@echo off
rem ============================================================
rem  KhoDongAI.bat - Mo AI ho tro hoc tap chi voi 1 cu dup chuot.
rem  1) Khoi dong server render Manim ngam (neu chua chay).
rem  2) Mo indexreal.html trong trinh duyet mac dinh.
rem  Khong can mo thu cong server.py nua.
rem ============================================================
wscript.exe "%~dp0start_server_hidden.vbs"
timeout /t 2 /nobreak >nul
start "" "%~dp0indexreal.html"
exit /b 0
