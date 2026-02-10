#!/bin/bash

# Azure Operator MCP Server - Quick Installation Script
# This script sets up the Azure Operator MCP server for local development

set -e

echo "🚀 Azure Operator MCP Server - Installation"
echo "=========================================="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✅ Found Python $PYTHON_VERSION"

# Check if in correct directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Please run this script from the mcp/azure-operator directory"
    exit 1
fi

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt --quiet

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "=========================================="
echo "1. Authenticate with Azure:"
echo "   az login"
echo ""
echo "2. Test the server:"
echo "   source venv/bin/activate"
echo "   python mcp_server.py"
echo ""
echo "3. Configure VSCode integration:"
echo "   See MCP_INSTALLATION_GUIDE.md for detailed instructions"
echo ""
echo "4. Try example prompts in GitHub Copilot:"
echo "   @azure-operator list all app services"
echo "   @azure-operator check AKS best practices"
echo ""
echo "For detailed instructions, see: MCP_INSTALLATION_GUIDE.md"
echo "=========================================="
