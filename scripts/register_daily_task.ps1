# Registers the daily content pass as a user-level Scheduled Task (no admin needed).
# Runs at 13:00 daily via pythonw (no console flash). The pass itself is the lowest-priority GPU tenant:
# it polls politely (6 x 10min) and exits quietly if the card never frees — tomorrow's pass retries.
$py = "C:\Users\bmhar\code\content-agent\.venv\Scripts\pythonw.exe"
$script = "C:\Users\bmhar\code\content-agent\run_daily.py"
schtasks /Create /F /TN "ContentAgentDaily" /SC DAILY /ST 13:00 `
  /TR "`"$py`" `"$script`"" | Out-Host
schtasks /Query /TN "ContentAgentDaily" /FO LIST | Out-Host
