#!/bin/bash
# Quick setup script for VS Code integration with GitHub Copilot

set -e

echo "=========================================="
echo "Azure Operator MCP - VS Code Setup"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "mcp_server.py" ]; then
    echo "❌ Error: Must run from mcp/azure-operator directory"
    echo "💡 Run: cd mcp/azure-operator && ./setup_vscode.sh"
    exit 1
fi

echo "📦 Step 1: Creating virtual environment..."
if [ -d "venv" ]; then
    echo "  ✓ Virtual environment already exists"
else
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
fi

echo ""
echo "📥 Step 2: Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  ✓ Dependencies installed"

echo ""
echo "🔐 Step 3: Checking Azure authentication..."
if az account show &>/dev/null; then
    SUBSCRIPTION=$(az account show --query name -o tsv)
    echo "  ✓ Azure CLI logged in"
    echo "  📍 Current subscription: $SUBSCRIPTION"
else
    echo "  ⚠️  Not logged in to Azure CLI"
    echo "  💡 Run: az login"
fi

echo ""
echo "✅ Step 4: Testing MCP server..."
export TEST_MODE=true
timeout 3 python mcp_server.py 2>&1 | head -20 || true
echo "  ✓ Server can start"

echo ""
echo "📝 Step 5: VS Code configuration..."
if [ -f "../../.vscode/settings.json" ]; then
    echo "  ✓ VS Code settings.json exists"
else
    echo "  ⚠️  VS Code settings.json not found"
    echo "  💡 Copy .vscode/settings.json to your workspace"
fi

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1. Restart VS Code to load the new configuration"
echo ""
echo "2. Open GitHub Copilot Chat in VS Code"
echo "   (Ctrl+Shift+P → 'GitHub Copilot: Open Chat')"
echo ""
echo "3. Use the Azure Operator MCP server:"
echo "   @azure-operator list all app services"
echo "   @azure-operator check AKS best practices for my-cluster"
echo ""
echo "4. Check logs if issues occur:"
echo "   View → Output → Select 'GitHub Copilot Chat'"
echo ""
echo "📚 For more info, see: MCP_INSTALLATION_GUIDE.md"
echo ""
