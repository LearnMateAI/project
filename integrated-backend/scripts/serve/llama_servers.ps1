# Serve the generator and the judge with llama-server on Windows (CPU), N slots each.
#
#   Download a llama.cpp release zip (llama-*-bin-win-cpu-x64.zip) and unzip it somewhere.
#   .\scripts\serve\llama_servers.ps1 -LlamaServer C:\tools\llama\llama-server.exe -Slots 2
#
# Same layout as llama_servers.sh; see there for why context is Slots x the window.
# On this laptop's CPU, parallel slots mostly trade latency for throughput -- the numbers
# for the paper come from the Mac.
param(
    [string]$LlamaServer = "llama-server.exe",
    [int]$Slots = 2,
    [int]$Threads = 8,
    [string]$ModelsDir = (Join-Path $PSScriptRoot "..\..\models"),
    [string]$GenGguf = "qwen2.5-3b-instruct-q4_k_m.gguf",
    [string]$JudgeGguf = "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    [int]$GenCtx = 4096,
    [int]$JudgeCtx = 8192
)

$logDir = Join-Path $PSScriptRoot "..\..\data\serve-logs"
New-Item -ItemType Directory -Force $logDir | Out-Null

$gen = Start-Process -FilePath $LlamaServer -PassThru -NoNewWindow `
    -RedirectStandardError (Join-Path $logDir "generator.log") `
    -ArgumentList @("-m", (Join-Path $ModelsDir $GenGguf), "--alias", "qwen25-3b",
                    "--host", "127.0.0.1", "--port", "8001", "-np", $Slots,
                    "-c", ($Slots * $GenCtx), "-t", $Threads, "--metrics")
$judge = Start-Process -FilePath $LlamaServer -PassThru -NoNewWindow `
    -RedirectStandardError (Join-Path $logDir "judge.log") `
    -ArgumentList @("-m", (Join-Path $ModelsDir $JudgeGguf), "--alias", "llama32-3b-judge",
                    "--host", "127.0.0.1", "--port", "8002", "-np", $Slots,
                    "-c", ($Slots * $JudgeCtx), "-t", $Threads, "--metrics")

Write-Host "Generator pid $($gen.Id) on :8001, judge pid $($judge.Id) on :8002 ($Slots slots each)."
Write-Host "Set LEARNMATE_GENERATOR_BACKEND=http / LEARNMATE_JUDGE_BACKEND=http (see llama_servers.sh)."
Write-Host "Press Enter to stop both."
[void][Console]::ReadLine()
Stop-Process -Id $gen.Id, $judge.Id -ErrorAction SilentlyContinue
