' run_hidden.vbs — Launch a .bat file with no visible console window.
'
' Usage (Task Scheduler action):
'   Execute:   wscript.exe
'   Arguments: "C:\...\scripts\run_hidden.vbs" "C:\...\scripts\run_ingest.bat"
'
' WshShell.Run parameters:
'   arg 1 — command string (quoted path to .bat)
'   arg 2 — window style: 0 = completely hidden (no taskbar button, no flash)
'   arg 3 — bWaitOnReturn: True = VBS blocks until bat exits.
'            Task Scheduler sees the task as "Running" the whole time, so
'            MultipleInstances=IgnoreNew correctly prevents overlapping runs.
'            ExecutionTimeLimit (1h) kills the bat if it hangs — intentional.
'
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """" & WScript.Arguments(0) & """", 0, True
