#!/bin/bash
# 오네시스 실행 (더블클릭용)
# Finder에서 이 파일을 두 번 클릭하면 앱이 켜지고 브라우저가 자동으로 열립니다.
# 종료하려면 열린 검은 창(터미널)을 닫거나 Ctrl+C 를 누르세요.

cd "$HOME/onesis" || { echo "onesis 폴더를 찾을 수 없습니다."; read; exit 1; }

# 서버가 뜨면(약 8초 뒤) 브라우저 자동 열기
( sleep 8; open "http://localhost:5173" ) &

exec ./run-dev.sh
