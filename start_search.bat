@echo off
chcp 65001 > nul
echo ======================================
echo  工務店URL一括検索（6並列）
echo ======================================
cd /d %~dp0

echo [Worker0] 北海道〜福島...
start "Worker0" python search_urls_fast.py --worker 0 --delay 5.0

timeout /t 2 /nobreak > nul
echo [Worker1] 栃木〜神奈川...
start "Worker1" python search_urls_fast.py --worker 1 --delay 5.0

timeout /t 2 /nobreak > nul
echo [Worker2] 富山〜愛知...
start "Worker2" python search_urls_fast.py --worker 2 --delay 5.0

timeout /t 2 /nobreak > nul
echo [Worker3] 三重〜鳥取...
start "Worker3" python search_urls_fast.py --worker 3 --delay 5.0

timeout /t 2 /nobreak > nul
echo [Worker4] 島根〜高知...
start "Worker4" python search_urls_fast.py --worker 4 --delay 5.0

timeout /t 2 /nobreak > nul
echo [Worker5] 福岡〜沖縄...
start "Worker5" python search_urls_fast.py --worker 5 --delay 5.0

echo.
echo 6つのウィンドウが起動しました。
echo 全ウィンドウが「完了」になったら merge_workers.py を実行してください。
echo.
pause
