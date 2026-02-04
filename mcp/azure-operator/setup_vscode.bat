@echo off
REM Quick setup script for VS Code integration with GitHub Copilot (Windows)

echo ==========================================
echo Azure Operator MCP - VS Code Setup
echo ==========================================
echo.

REM Check if we're in the right directory
if not exist "mcp_server.py" (
    echo Error: Must run from mcp\azure-operator directory
    echo Run: cd mcp\azure-operator ^&^& setup_vscode.bat
    exit /b 1
)

echo Step 1: Creating virtual environment...
if exist "venv\" (
    echo   Virtual environment already exists
) else (
    python -m venv venv
    echo   Virtual environment created
)

echo.
echo Step 2: Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
echo   Dependencies installed

echo.
echo Step 3: Checking Azure authentication...
az account show >nul 2>&1
if %errorlevel% equ 0 (
    echo   Azure CLI logged in
    for /f "tokens=*" %%i in ('az account show --query name -o tsv') do set SUBSCRIPTION=%%i
    echo   Current subscription: %SUBSCRIPTION%
) else (
    echo   Not logged in to Azure CLI
    echo   Run: az login
)

echo.
echo Step 4: Testing MCP server...
set TEST_MODE=true
timeout /t 3 /nobreak >nul 2>&1 & python mcp_server.py 2>&1 | findstr /n "^" | findstr /r "^[1-9]:" || echo   Server can start
echo.

echo Step 5: VS Code configuration...
if exist "..\..\vscode\settings.json" (
    echo   VS Code settings.json exists
) else (
    echo   VS Code settings.json not found
    echo   Copy .vscode\settings.json to your workspace
)

echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo Next Steps:
echo.
echo 1. Restart VS Code to load the new configuration
echo.
echo 2. Open GitHub Copilot Chat in VS Code
echo    (Ctrl+Shift+P - GitHub Copilot: Open Chat)
echo.
echo 3. Use the Azure Operator MCP server:
echo    @azure-operator list all app services
echo    @azure-operator check AKS best practices for my-cluster
echo.
echo 4. Check logs if issues occur:
echo    View - Output - Select 'GitHub Copilot Chat'
echo.
echo For more info, see: MCP_INSTALLATION_GUIDE.md
echo.

pause
