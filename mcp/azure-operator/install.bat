@echo off
REM Azure Operator MCP Server - Quick Installation Script for Windows

echo.
echo Azure Operator MCP Server - Installation
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed. Please install Python 3.11 or higher.
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Check if in correct directory
if not exist requirements.txt (
    echo ERROR: Please run this script from the mcp\azure-operator directory
    exit /b 1
)

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo Installation complete!
echo.
echo Next steps:
echo ==========================================
echo 1. Authenticate with Azure:
echo    az login
echo.
echo 2. Test the server:
echo    venv\Scripts\activate.bat
echo    python mcp_server.py
echo.
echo 3. Configure VSCode integration:
echo    See MCP_INSTALLATION_GUIDE.md for detailed instructions
echo.
echo 4. Try example prompts in GitHub Copilot:
echo    @azure-operator list all app services
echo    @azure-operator check AKS best practices
echo.
echo For detailed instructions, see: MCP_INSTALLATION_GUIDE.md
echo ==========================================
echo.

pause
