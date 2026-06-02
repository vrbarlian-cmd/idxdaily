' run_hidden.vbs — Launch a .bat file with no visible console window.
'
' Usage (Task Scheduler action):
'   Execute : wscript.exe
'   Arguments: "C:\...\scripts\run_hidden.vbs" "C:\...\scripts\run_ingest.bat"
'
' Window style 0 = completely hidden (no taskbar button, no flash).
' bWaitOnReturn = True so Task Scheduler tracks the task as "Running"
' until the .bat exits, which lets MultipleInstances=IgnoreNew work correctly
' and makes LastTaskResult reflect the actual exit code.
'
Set objShell = CreateObject("WScript.Shell")
exitCode = objShell.Run("""" & WScript.Arguments(0) & """", 0, True)
WScript.Quit exitCode
