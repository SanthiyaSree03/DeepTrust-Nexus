# PowerShell script to reliably download and install PyTorch CUDA with auto-resume
$ErrorActionPreference = "Stop"
$aiDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $aiDir

$torchWheel = "torch-2.6.0+cu124-cp313-cp313-win_amd64.whl"
$torchUrl = "https://download.pytorch.org/whl/cu124/torch-2.6.0%2Bcu124-cp313-cp313-win_amd64.whl"

$visionWheel = "torchvision-0.21.0+cu124-cp313-cp313-win_amd64.whl"
$visionUrl = "https://download.pytorch.org/whl/cu124/torchvision-0.21.0%2Bcu124-cp313-cp313-win_amd64.whl"

Write-Host "=== Step 1/3: Downloading PyTorch CUDA Wheel (with auto-resume) ==="
curl.exe -L -C - --retry 25 --retry-delay 5 --retry-connrefused -o $torchWheel $torchUrl

Write-Host "=== Step 2/3: Downloading Torchvision CUDA Wheel ==="
curl.exe -L -C - --retry 25 --retry-delay 5 --retry-connrefused -o $visionWheel $visionUrl

Write-Host "=== Step 3/3: Installing into Python Environment ==="
& ".\venv\Scripts\python.exe" -m pip install --force-reinstall $torchWheel $visionWheel

Write-Host "=== Verifying CUDA GPU Acceleration ==="
& ".\venv\Scripts\python.exe" -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('GPU Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

Write-Host "=== Cleaning up local wheel files ==="
Remove-Item -Force $torchWheel, $visionWheel -ErrorAction SilentlyContinue

Write-Host "=== PYTORCH CUDA GPU INSTALLATION COMPLETE! ==="
