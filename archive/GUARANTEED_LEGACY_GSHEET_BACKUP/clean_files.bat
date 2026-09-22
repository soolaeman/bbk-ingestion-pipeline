@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
:: Berpindah ke direktori kerja utama
cd /d "G:\My Drive\Automation"

:: Menjalankan skrip Python pembersihan
echo Sedang menjalankan proses pengarsipan foto dan pembersihan Google Sheets...
echo.

:: Menjalankan skrip
python clean_files.py

:: Menunggu input agar jendela tidak langsung tertutup jika terjadi error
echo.
echo Proses selesai.
pause