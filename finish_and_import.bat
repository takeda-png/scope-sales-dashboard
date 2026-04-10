@echo off
chcp 65001 > nul
echo ======================================
echo  マージ＆companies.csvインポート
echo ======================================
cd /d %~dp0

echo [1/2] ワーカー結果をマージ中...
python merge_workers.py

echo.
echo [2/2] companies.csvにインポート中...
python import_builders.py

echo.
echo 完了！次のコマンドで送信開始できます:
echo   node pipeline.js
echo.
pause
