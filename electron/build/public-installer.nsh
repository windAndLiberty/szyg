; The stock electron-builder updater attempts a graceful close later in the
; install flow. Older releases may be hidden in the tray, so close and
; then terminate the known process before that check runs.
!macro customInit
  DetailPrint "正在关闭已运行的小妤 AI…"
  ${nsProcess::CloseProcess} "XiaoyuAI.exe" $0
  Sleep 700
  ${nsProcess::KillProcess} "XiaoyuAI.exe" $0
  ${nsProcess::Unload}
!macroend
