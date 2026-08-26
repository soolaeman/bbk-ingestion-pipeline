@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

:: Masuk ke direktori folder Automation di Google Drive (Drive G:)
cd /d "G:\My Drive\Automation"

:: Jalankan run.py dari direktori tersebut
python run.py

pause