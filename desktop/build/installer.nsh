; Daybook's background service (daybook-backend.exe) keeps running after the window closes, so its files
; are locked during an update or uninstall. Stop it first; Daybook starts it again when it opens.
; No /T: the service may have started Ollama, which must keep running.
!macro customInit
  nsExec::Exec 'taskkill /F /IM daybook-backend.exe'
  nsExec::Exec 'taskkill /F /IM daybook-mcp.exe'
  Sleep 1000
!macroend
!macro customUnInit
  nsExec::Exec 'taskkill /F /IM daybook-backend.exe'
  nsExec::Exec 'taskkill /F /IM daybook-mcp.exe'
  Sleep 1000
!macroend
