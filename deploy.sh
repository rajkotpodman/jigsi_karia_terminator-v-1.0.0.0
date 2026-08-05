#!/usr/bin/env bash
# ==============================================================================
# ⚡ JIGSI KARIA TERMINATOR - ENTERPRISE CLI DEPLOYMENT & ORCHESTRATOR
# ==============================================================================
set -e

# Colors for Terminal UI
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_banner() {
    clear
    echo -e "${PURPLE}==============================================================================${NC}"
    echo -e "${CYAN}     ⚡ JIGSI KARIA TERMINATOR - MULTI-PLATFORM ORCHESTRATOR ⚡${NC}"
    echo -e "${PURPLE}==============================================================================${NC}"
    echo -e " Supported Targets: ${GREEN}Web | Electron | Tauri | Capacitor | Docker${NC}"
    echo -e "${PURPLE}==============================================================================${NC}\n"
}

detect_os() {
    OS="unknown"
    ARCH=$(uname -m)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        OS="windows"
    fi
    echo -e "🔍 Detected Operating System: ${GREEN}${OS^^} (${ARCH})${NC}"
}

check_prerequisites() {
    echo -e "\n${YELLOW}[*] Checking System Prerequisites...${NC}"
    
    # Check Node.js
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node -v)
        echo -e "  ✅ Node.js: ${GREEN}${NODE_VERSION}${NC}"
    else
        echo -e "  ❌ Node.js: ${RED}NOT FOUND${NC} (Required for web/electron/tauri)"
    fi

    # Check npm
    if command -v npm &> /dev/null; then
        NPM_VERSION=$(npm -v)
        echo -e "  ✅ npm: ${GREEN}${NPM_VERSION}${NC}"
    else
        echo -e "  ❌ npm: ${RED}NOT FOUND${NC}"
    fi

    # Check Rust / Cargo
    if command -v cargo &> /dev/null; then
        CARGO_VERSION=$(cargo --version)
        echo -e "  ✅ Rust Cargo: ${GREEN}${CARGO_VERSION}${NC}"
    else
        echo -e "  ⚠️  Rust Cargo: ${YELLOW}NOT FOUND${NC} (Required for Tauri builds)"
    fi

    # Check Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | head -n 1)
        echo -e "  ✅ Docker: ${GREEN}${DOCKER_VERSION}${NC}"
    else
        echo -e "  ⚠️  Docker: ${YELLOW}NOT FOUND${NC} (Required for containerization)"
    fi

    # Check Android SDK
    if command -v adb &> /dev/null || [ -n "$ANDROID_HOME" ]; then
        echo -e "  ✅ Android SDK: ${GREEN}FOUND${NC}"
    else
        echo -e "  ⚠️  Android SDK: ${YELLOW}NOT FOUND${NC} (Required for Android APK builds)"
    fi
    
    # Check Package Managers
    if command -v brew &> /dev/null; then
        echo -e "  ✅ Homebrew: ${GREEN}FOUND${NC}"
    elif command -v apt-get &> /dev/null; then
        echo -e "  ✅ APT: ${GREEN}FOUND${NC}"
    fi
}

install_node_deps() {
    echo -e "\n${BLUE}[+] Installing Node.js dependencies...${NC}"
    npm install
}

target_dev_mode() {
    print_banner
    echo -e "${CYAN}🌐 Launching Dev Mode (Express + React/Web Gateway)...${NC}"
    install_node_deps
    echo -e "${GREEN}[+] Starting server.js on port 3000...${NC}"
    node server.js
}

target_desktop_mode() {
    print_banner
    echo -e "${CYAN}🪟 Launching Desktop Mode (Electron Local Host)...${NC}"
    install_node_deps
    npx electron electron-main.js
}

target_tauri_mode() {
    print_banner
    echo -e "${CYAN}🦀 Launching Lightweight Native Mode (Tauri Rust App)...${NC}"
    install_node_deps
    npm run tauri dev
}

target_mobile_mode() {
    print_banner
    echo -e "${CYAN}📱 Launching Mobile Emulator Mode (Capacitor Android)...${NC}"
    install_node_deps
    npx cap run android
}

target_container_mode() {
    print_banner
    echo -e "${CYAN}🐳 Launching Container Mode (Docker Desktop Stack)...${NC}"
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed or running.${NC}"
    else
        docker build -t jigsi-karia-terminator:latest .
        echo -e "${GREEN}✅ Docker image built successfully!${NC}"
        echo "Running container on port 3000..."
        docker run --rm -p 3000:3000 jigsi-karia-terminator:latest
    fi
    read -p "Press Enter to return to menu..."
}

target_enterprise_packaging() {
    print_banner
    echo -e "${CYAN}📦 Enterprise Production Packaging (Build all installers for current OS)...${NC}"
    install_node_deps
    npm run build
    
    if [[ "$OS" == "linux" ]]; then
        if [ -f "./build-linux-packages.sh" ]; then
            bash build-linux-packages.sh
        else
            echo "build-linux-packages.sh not found."
        fi
    elif [[ "$OS" == "macos" ]]; then
        if [ -f "./create-dmg.sh" ]; then
            bash create-dmg.sh
        else
            echo "create-dmg.sh not found."
        fi
    elif [[ "$OS" == "windows" ]]; then
         echo -e "${CYAN}🪟 Please use deploy.ps1 for Windows builds.${NC}"
    fi
    echo -e "${GREEN}✅ Packaging tasks completed!${NC}"
    read -p "Press Enter to return to menu..."
}

main_menu() {
    while true; do
        print_banner
        detect_os
        check_prerequisites
        
        echo -e "\n${PURPLE}==============================================================================${NC}"
        echo -e " ${YELLOW}Select Action / Target Platform:${NC}"
        echo -e "${PURPLE}==============================================================================${NC}"
        echo " [1] Dev Mode (Express + React/Web Gateway)"
        echo " [2] Desktop Mode (Electron Local Host)"
        echo " [3] Lightweight Native Mode (Tauri Rust App)"
        echo " [4] Mobile Emulator Mode (Capacitor Android)"
        echo " [5] Container Mode (Docker Desktop Stack)"
        echo " [6] Enterprise Production Packaging (Build all installers for current OS)"
        echo " [7] Exit"
        echo -e "${PURPLE}==============================================================================${NC}"
        read -p "Enter your choice [1-7]: " choice

        case $choice in
            1) target_dev_mode ;;
            2) target_desktop_mode ;;
            3) target_tauri_mode ;;
            4) target_mobile_mode ;;
            5) target_container_mode ;;
            6) target_enterprise_packaging ;;
            7) echo -e "\n${GREEN}Exiting Jigsi Karia Terminator Orchestrator. Goodbye!${NC}\n"; exit 0 ;;
            *) echo -e "${RED}Invalid option. Please choose 1-7.${NC}"; sleep 2 ;;
        esac
    done
}

main_menu
