' run_hidden.vbs — Launch a .bat file with no visible console window.
'
' Usage (Task Scheduler action):
'   Execute:   wscript.exe
'   Arguments: "C:\...\scripts\run_hidden.vbs" "C:\...\scripts\run_ingest.bat"
'
' WshShell.Run parameters:
'   arg 1 — command string (quoted path to .bat)
'   arg 2 — window style: 0 = completely hidden (no taskbar button, no flash)
'   arg 3 — bWaitOnReturn: False = fire-and-forget (wscript exits immediately,
'            bat runs as a detached hidden process)
'            This prevents Task Scheduler's ExecutionTimeLimit from sending a
'            kill signal to the bat mid-run (which caused STATUS_CONTROL_C_EXIT).
'
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """" & WScript.Arguments(0) & """", 0, False
