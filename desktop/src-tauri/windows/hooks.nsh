; Stop desktop + sidecar/daemon before install replace or uninstall remove.
; See https://v2.tauri.app/distribute/windows-installer/#extending-the-installer

!macro _NavbeStopAll
  DetailPrint "Stopping Navbe processes..."
  ${If} ${FileExists} "$INSTDIR\resources\stop-all.cmd"
    nsExec::ExecToLog '"$INSTDIR\resources\stop-all.cmd"'
  ${Else}
    nsExec::ExecToLog 'taskkill /F /IM navbe-desktop.exe /T'
    nsExec::ExecToLog 'taskkill /F /IM navbe.exe /T'
    Delete "$PROFILE\.navbe\serve.pid"
  ${EndIf}
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro _NavbeStopAll
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro _NavbeStopAll
!macroend
