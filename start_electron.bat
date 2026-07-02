@echo off
set NODE_ENV=development
cd /d D:\szyg\electron
D:\szyg\electron\node_modules\electron\dist\electron.exe . --remote-debugging-port=9222 --remote-allow-origins=*
