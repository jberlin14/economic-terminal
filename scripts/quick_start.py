#!/usr/bin/env python3
"""
Quick Start Script

Quickly set up the Economic Terminal for first-time use.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Color codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 60}{Colors.END}\n")

def print_step(step, total, text):
    """Print step"""
    print(f"{Colors.BOLD}[{step}/{total}] {text}{Colors.END}")

def check_env_file():
    """Check if .env file exists"""
    env_path = project_root / '.env'
    if not env_path.exists():
        print(f"{Colors.YELLOW}No .env file found!{Colors.END}")
        print("Copying .env.example to .env...")

        example_path = project_root / '.env.example'
        if example_path.exists():
            import shutil
            shutil.copy(example_path, env_path)
            print(f"{Colors.GREEN}Created .env file{Colors.END}")
            print(f"\n{Colors.YELLOW}IMPORTANT: Edit .env and add your API keys:{Colors.END}")
            print("  - FRED_API_KEY (required)")
            print("  - ALPHA_VANTAGE_KEY (optional)")
            print("  - SENDGRID_API_KEY (optional)")
            return False
        else:
            print(f"{Colors.RED}Error: .env.example not found!{Colors.END}")
            return False
    return True

def run_script(script_name, description):
    """Run a Python script"""
    print(f"  {description}...")
    try:
        script_path = project_root / 'scripts' / script_name
        subprocess.run([sys.executable, str(script_path)], check=True)
        print(f"  {Colors.GREEN}✓ Complete{Colors.END}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  {Colors.RED}✗ Failed: {e}{Colors.END}")
        return False
    except FileNotFoundError:
        print(f"  {Colors.RED}✗ Script not found: {script_name}{Colors.END}")
        return False

def main():
    """Run quick start setup"""
    print_header("ECONOMIC TERMINAL - QUICK START")

    print(f"{Colors.BOLD}This script will set up your Economic Terminal.{Colors.END}\n")

    # Step 1: Check environment
    print_step(1, 5, "Checking environment configuration")
    if not check_env_file():
        print(f"\n{Colors.YELLOW}Please edit .env file and run this script again.{Colors.END}\n")
        return 1

    # Verify API keys are set
    from dotenv import load_dotenv
    load_dotenv()

    fred_key = os.getenv('FRED_API_KEY')
    if not fred_key or fred_key == 'your_fred_api_key_here':
        print(f"\n{Colors.RED}ERROR: FRED_API_KEY not configured in .env file{Colors.END}")
        print("Get a free API key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        print("Then edit .env and run this script again.\n")
        return 1

    print(f"  {Colors.GREEN}✓ Environment configured{Colors.END}\n")

    # Step 2: Initialize database
    print_step(2, 5, "Initializing database")
    if not run_script('init_db.py', 'Creating database tables'):
        return 1
    print()

    # Step 3: Add performance indexes
    print_step(3, 5, "Adding performance indexes")
    if not run_script('add_indexes.py', 'Creating database indexes'):
        return 1
    print()

    # Step 4: Initialize indicators
    print_step(4, 5, "Initializing economic indicators")
    print(f"  {Colors.YELLOW}This will take 2-3 minutes...{Colors.END}")
    if not run_script('init_indicators.py', 'Fetching indicator metadata and data'):
        print(f"  {Colors.YELLOW}Warning: Some indicators may have failed{Colors.END}")
        print(f"  {Colors.YELLOW}This is normal for deprecated series{Colors.END}")
    print()

    # Step 5: Health check
    print_step(5, 5, "Running health check")
    run_script('health_check.py', 'Verifying system health')
    print()

    # Success!
    print_header("SETUP COMPLETE!")

    print(f"{Colors.GREEN}{Colors.BOLD}Your Economic Terminal is ready!{Colors.END}\n")

    print(f"{Colors.BOLD}Next steps:{Colors.END}")
    print(f"\n1. Start the backend:")
    print(f"   {Colors.BLUE}uvicorn backend.main:app --reload{Colors.END}")

    print(f"\n2. In another terminal, start the frontend:")
    print(f"   {Colors.BLUE}cd frontend{Colors.END}")
    print(f"   {Colors.BLUE}npm install{Colors.END}")
    print(f"   {Colors.BLUE}npm start{Colors.END}")

    print(f"\n3. Open your browser:")
    print(f"   {Colors.BLUE}http://localhost:3000{Colors.END}")

    print(f"\n{Colors.YELLOW}The scheduler will automatically fetch updates every few minutes.{Colors.END}")
    print(f"{Colors.YELLOW}You can manually fetch data using:{Colors.END}")
    print(f"   {Colors.BLUE}python scripts/manual_fetch.py{Colors.END}\n")

    return 0

if __name__ == '__main__':
    sys.exit(main())
