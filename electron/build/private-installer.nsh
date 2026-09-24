; The stock electron-builder updater attempts a graceful close later in the
; install flow. Older private editions may be hidden in the tray, so close and
; then terminate the known process before that check runs.
!macro customInit
  DetailPrint "正在关闭已运行的数字员工…"
  ${nsProcess::CloseProcess} "数字员工.exe" $0
  Sleep 700
  ${nsProcess::KillProcess} "数字员工.exe" $0
  ${nsProcess::Unload}
!macroend
