' szyg Desktop Launcher — Chrome app mode
' Double-click this file to start szyg

Set WshShell = CreateObject("WScript.Shell")

' Start backend
WshShell.Run "cmd /c cd /d C:\szyg && start /min cmd /c ""set PYTHONPATH=C:\szyg\server && set SZYG_DATA_DIR=C:\szyg\data && C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe -m uvicorn szyg.api.app:create_app --host 127.0.0.1 --port 8000 --factory""", 0, False

' Wait for backend
WScript.Sleep 4000

' Open Chrome in app mode (frameless window)
On Error Resume Next
WshShell.Run "chrome --app=http://127.0.0.1:8000/login --window-size=1300,760 --disable-cache --new-window", 1, False
If Err.Number <> 0 Then
    WshShell.Run "msedge --app=http://127.0.0.1:8000/login --window-size=1300,760", 1, False
End If
On Error Goto 0
