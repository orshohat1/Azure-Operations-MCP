#!/usr/bin/env python3
"""
Validation script for Azure Operator MCP Server
Tests that everything is properly configured and can run
"""

import sys
import os
import subprocess
import importlib.util

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓{RESET} {text}")

def print_error(text):
    print(f"{RED}✗{RESET} {text}")

def print_warning(text):
    print(f"{YELLOW}⚠{RESET} {text}")

def check_python_version():
    """Check if Python version is 3.11+"""
    version = sys.version_info
    if version >= (3, 11):
        print_success(f"Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python version: {version.major}.{version.minor}.{version.micro} (3.11+ required)")
        return False

def check_module(module_name):
    """Check if a Python module is installed"""
    spec = importlib.util.find_spec(module_name)
    if spec is not None:
        print_success(f"Module '{module_name}' is installed")
        return True
    else:
        print_error(f"Module '{module_name}' is NOT installed")
        return False

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print_success(f"{description}: {filepath}")
        return True
    else:
        print_error(f"{description} NOT FOUND: {filepath}")
        return False

def check_azure_cli():
    """Check if Azure CLI is installed and logged in"""
    try:
        result = subprocess.run(['az', '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            print_success("Azure CLI is installed")
            
            # Check if logged in
            result = subprocess.run(['az', 'account', 'show'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                print_success("Azure CLI is logged in")
                return True
            else:
                print_warning("Azure CLI is installed but not logged in")
                print(f"         Run: az login")
                return True  # Not an error, just a warning
        else:
            print_error("Azure CLI not working properly")
            return False
    except FileNotFoundError:
        print_warning("Azure CLI not found (optional for TEST_MODE)")
        return True
    except Exception as e:
        print_warning(f"Could not check Azure CLI: {e}")
        return True

def test_imports():
    """Test that all required modules can be imported"""
    print_header("Testing Module Imports")
    
    modules = [
        'azure.identity',
        'azure.mgmt.web',
        'azure.mgmt.monitor',
        'azure.mgmt.containerservice',
        'mcp',
        'mcp.server',
        'fastapi',
        'pydantic',
    ]
    
    all_ok = True
    for module in modules:
        all_ok &= check_module(module)
    
    return all_ok

def test_local_modules():
    """Test that local modules can be imported"""
    print_header("Testing Local Modules")
    
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    modules = ['auth', 'models', 'utils', 'app_service_tools', 'aks_tools', 'best_practices_tools']
    
    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print_success(f"Local module '{module}' imports successfully")
        except Exception as e:
            print_error(f"Local module '{module}' failed: {e}")
            all_ok = False
    
    return all_ok

def test_file_structure():
    """Test that all required files exist"""
    print_header("Testing File Structure")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    files = [
        ('mcp_server.py', 'MCP Server'),
        ('auth.py', 'Authentication module'),
        ('models.py', 'Models module'),
        ('utils.py', 'Utils module'),
        ('app_service_tools.py', 'App Service tools'),
        ('aks_tools.py', 'AKS tools'),
        ('best_practices_tools.py', 'Best practices tools'),
        ('requirements.txt', 'Requirements file'),
        ('.env.example', 'Environment example'),
        ('__init__.py', 'Package init'),
        ('__main__.py', 'Main entry point'),
    ]
    
    all_ok = True
    for filename, description in files:
        filepath = os.path.join(base_dir, filename)
        all_ok &= check_file_exists(filepath, description)
    
    return all_ok

def test_mcp_server():
    """Test that MCP server can start"""
    print_header("Testing MCP Server Startup")
    
    try:
        # Set TEST_MODE to avoid Azure connection
        env = os.environ.copy()
        env['TEST_MODE'] = 'true'
        env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
        
        # Try to start server with timeout
        result = subprocess.run(
            [sys.executable, 'mcp_server.py'],
            capture_output=True,
            text=True,
            timeout=5,
            env=env
        )
        
        print_error("Server didn't timeout (expected)")
        return False
        
    except subprocess.TimeoutExpired as e:
        # Timeout is expected - server runs indefinitely
        output = e.stdout.decode() if e.stdout else ""
        error_output = e.stderr.decode() if e.stderr else ""
        combined_output = output + error_output
        
        if "Azure Operator MCP Server" in combined_output or "Ready to accept connections" in combined_output:
            print_success("MCP server starts successfully")
            if "TEST MODE" in combined_output:
                print_success("  Running in TEST MODE")
            return True
        else:
            print_error("MCP server started but output unexpected")
            if combined_output:
                print(f"Output: {combined_output[:300]}")
            return False
    except Exception as e:
        print_error(f"MCP server failed to start: {e}")
        return False

def main():
    """Run all validation tests"""
    print_header("🔍 Azure Operator MCP Server - Validation Tests")
    
    results = []
    
    # Python version
    print_header("Checking Python Version")
    results.append(("Python Version", check_python_version()))
    
    # File structure
    results.append(("File Structure", test_file_structure()))
    
    # Python modules
    results.append(("Required Modules", test_imports()))
    
    # Local modules
    results.append(("Local Modules", test_local_modules()))
    
    # Azure CLI
    print_header("Checking Azure CLI")
    results.append(("Azure CLI", check_azure_cli()))
    
    # MCP Server
    results.append(("MCP Server", test_mcp_server()))
    
    # Summary
    print_header("📊 Validation Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        if result:
            print_success(f"{name}")
        else:
            print_error(f"{name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print(f"\n{GREEN}✅ All validations passed! Server is ready to use.{RESET}\n")
        return 0
    else:
        print(f"\n{RED}❌ Some validations failed. Please fix the issues above.{RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
