<#
.SYNOPSIS
    ⚡ JIGSI KARIA TERMINATOR - ENTERPRISE POWERSHELL DEPLOYMENT ORCHESTRATOR
#>

$Host.UI.RawUI.ForegroundColor = "Cyan"
Clear-Host

function Show-Banner {
    Clear-Host
    Write-Host "==============================================================================" -ForegroundColor Magenta
    Write-Host "     ⚡ JIGSI KARIA TERMINATOR - WINDOWS POWERHELL ORCHESTRATOR ⚡" -ForegroundColor Cyan
    Write-Host "==============================================================================" -ForegroundColor Magenta
    Write-Host " Supported Targets: Web | Electron | Tauri | Capacitor | Docker" -ForegroundColor Green
    Write-Host "==============================================================================" -ForegroundColor Magenta
    Write-Host ""
}

function Test-Prerequisites {
    Write-Host "[*] Checking System Prerequisites..." -ForegroundColor Yellow
    
    if (Get-Command node -ErrorAction SilentlyContinue) {
        $nodeVer = node -v
        Write-Host "  [+] Node.js: $nodeVer" -ForegroundColor Green
    } else {
        Write-Host "  [-] Node.js: NOT FOUND (Required)" -ForegroundColor Red
    }

    if (Get-Command npm -ErrorAction SilentlyContinue) {
        $npmVer = npm -v
        Write-Host "  [+] npm: $npmVer" -ForegroundColor Green
    } else {
        Write-Host "  [-] npm: NOT FOUND" -ForegroundColor Red
    }

    if (Get-Command rustc -ErrorAction SilentlyContinue) {
        $rustVer = rustc --version
        Write-Host "  [+] Rust: $rustVer" -ForegroundColor Green
    } else {
        Write-Host "  [-] Rust: NOT FOUND" -ForegroundColor Red
    }

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Host "  [+] Docker: FOUND" -ForegroundColor Green
    } else {
        Write-Host "  [-] Docker: NOT FOUND" -ForegroundColor Red
    }

    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Host "  [+] Choco: FOUND" -ForegroundColor Green
    } else {
        Write-Host "  [-] Choco: NOT FOUND" -ForegroundColor Red
    }
}

function Invoke-DevMode {
    Show-Banner
    Write-Host "🌐 Launching Dev Mode (Express + React/Web Gateway)..." -ForegroundColor Cyan
    npm install
    node server.js
}

function Invoke-DesktopMode {
    Show-Banner
    Write-Host "🪟 Launching Desktop Mode (Electron Local Host)..." -ForegroundColor Cyan
    npm install
    npx electron electron-main.js
}

function Invoke-TauriMode {
    Show-Banner
    Write-Host "🦀 Launching Lightweight Native Mode (Tauri Rust App)..." -ForegroundColor Cyan
    npm install
    npm run tauri dev
}

function Invoke-MobileMode {
    Show-Banner
    Write-Host "📱 Launching Mobile Emulator Mode (Capacitor Android)..." -ForegroundColor Cyan
    npm install
    npx cap run android
}

function Invoke-ContainerMode {
    Show-Banner
    Write-Host "🐳 Launching Container Mode (Docker Desktop Stack)..." -ForegroundColor Cyan
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        docker build -t jigsi-karia-terminator:latest .
        Write-Host "✅ Docker image built successfully!" -ForegroundColor Green
        docker run --rm -p 3000:3000 jigsi-karia-terminator:latest
    } else {
        Write-Host "[-] Docker is not installed." -ForegroundColor Red
    }
    Read-Host "Press Enter to return to menu..."
}

function Invoke-EnterprisePackaging {
    Show-Banner
    Write-Host "📦 Enterprise Production Packaging (Build all installers)..." -ForegroundColor Cyan
    npm install
    npm run build
    if (Get-Command makensis -ErrorAction SilentlyContinue) {
        makensis installer.nsi
        Write-Host "✅ Windows NSIS Installer built successfully!" -ForegroundColor Green
    } else {
        Write-Host "[-] makensis not found. Install NSIS via 'choco install nsis'." -ForegroundColor Red
    }
    Read-Host "Press Enter to return to menu..."
}

function Main-Menu {
    while ($true) {
        Show-Banner
        Test-Prerequisites
        Write-Host ""
        Write-Host "==============================================================================" -ForegroundColor Magenta
        Write-Host " Select Action / Target Platform:" -ForegroundColor Yellow
        Write-Host "==============================================================================" -ForegroundColor Magenta
        Write-Host " [1] Dev Mode (Express + React/Web Gateway)"
        Write-Host " [2] Desktop Mode (Electron Local Host)"
        Write-Host " [3] Lightweight Native Mode (Tauri Rust App)"
        Write-Host " [4] Mobile Emulator Mode (Capacitor Android)"
        Write-Host " [5] Container Mode (Docker Desktop Stack)"
        Write-Host " [6] Enterprise Production Packaging (Build all installers for current OS)"
        Write-Host " [7] Exit"
        Write-Host "==============================================================================" -ForegroundColor Magenta
        
        $choice = Read-Host "Enter your choice [1-7]"
        switch ($choice) {
            "1" { Invoke-DevMode }
            "2" { Invoke-DesktopMode }
            "3" { Invoke-TauriMode }
            "4" { Invoke-MobileMode }
            "5" { Invoke-ContainerMode }
            "6" { Invoke-EnterprisePackaging }
            "7" { Write-Host "Exiting..." -ForegroundColor Green; exit }
            default { Write-Host "Invalid choice. Please select 1-7." -ForegroundColor Red; Start-Sleep -Seconds 2 }
        }
    }
}

Main-Menu
