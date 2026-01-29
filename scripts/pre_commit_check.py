#!/usr/bin/env python3
"""
Pre-Commit Check

Run this before committing to Git to ensure everything is ready.
"""

import sys
import os
from pathlib import Path
import subprocess

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

def check(name, passed, message=""):
    """Print check result"""
    icon = f"{Colors.GREEN}[+]{Colors.END}" if passed else f"{Colors.RED}[x]{Colors.END}"
    status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}FAIL{Colors.END}"
    print(f"{icon} {name}: {status} {message}")
    return passed

def main():
    """Run pre-commit checks"""
    print(f"\n{Colors.BOLD}Pre-Commit Checklist{Colors.END}\n")

    all_passed = True

    # 1. Check .env.example exists
    all_passed &= check(
        ".env.example",
        (project_root / '.env.example').exists(),
        "- Contains example configuration"
    )

    # 2. Check no .env in git
    try:
        result = subprocess.run(
            ['git', 'check-ignore', '.env'],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        env_ignored = result.returncode == 0
        all_passed &= check(
            ".env ignored",
            env_ignored,
            "- Sensitive file not tracked" if env_ignored else "- WARNING: Add to .gitignore!"
        )
    except:
        all_passed &= check(".env ignored", False, "- Cannot verify (git not available)")

    # 3. Check requirements.txt
    all_passed &= check(
        "requirements.txt",
        (project_root / 'requirements.txt').exists(),
        "- Dependencies documented"
    )

    # 4. Check README.md
    readme = project_root / 'README.md'
    if readme.exists():
        content = readme.read_text()
        has_install = 'installation' in content.lower()
        has_api_keys = 'api' in content.lower()
        all_passed &= check(
            "README.md",
            has_install and has_api_keys,
            "- Has installation and API key info"
        )
    else:
        all_passed &= check("README.md", False, "- Missing!")

    # 5. Check deployment docs
    all_passed &= check(
        "RENDER_DEPLOYMENT.md",
        (project_root / 'RENDER_DEPLOYMENT.md').exists(),
        "- Deployment guide present"
    )

    # 6. Check render.yaml
    all_passed &= check(
        "render.yaml",
        (project_root / 'render.yaml').exists(),
        "- IaC configuration present"
    )

    # 7. Check CHANGELOG.md
    all_passed &= check(
        "CHANGELOG.md",
        (project_root / 'CHANGELOG.md').exists(),
        "- Version history documented"
    )

    # 8. Check for large files
    try:
        # Check for database files
        db_files = list(project_root.glob('*.db'))
        if db_files:
            print(f"{Colors.YELLOW}⚠ WARNING: Database files found{Colors.END}")
            for db_file in db_files:
                print(f"  {db_file.name} - Add to .gitignore!")
        else:
            check("No .db files", True, "- Database not tracked")
    except:
        pass

    # 9. Check for __pycache__
    pycache_files = list(project_root.glob('**/__pycache__'))
    if pycache_files and not any('.gitignore' in str(p) for p in project_root.glob('.gitignore')):
        print(f"{Colors.YELLOW}⚠ WARNING: __pycache__ directories found{Colors.END}")
        print("  Add __pycache__/ to .gitignore")
    else:
        check("No __pycache__", True, "- Python cache not tracked")

    # 10. Check for node_modules
    node_modules = project_root / 'frontend' / 'node_modules'
    if node_modules.exists():
        # Should be in .gitignore
        try:
            result = subprocess.run(
                ['git', 'check-ignore', 'frontend/node_modules'],
                cwd=project_root,
                capture_output=True,
                text=True
            )
            ignored = result.returncode == 0
            check("node_modules ignored", ignored, "- Frontend deps not tracked" if ignored else "- Add to .gitignore!")
        except:
            pass
    else:
        check("node_modules", True, "- Not present or ignored")

    # 11. Check for sensitive info in code
    sensitive_patterns = ['password', 'api_key', 'secret', 'token']
    print(f"\n{Colors.BLUE}Scanning for sensitive patterns...{Colors.END}")

    found_sensitive = False
    for pattern in sensitive_patterns:
        try:
            # Only check .py and .tsx files
            for ext in ['*.py', '*.tsx', '*.ts']:
                files = project_root.glob(f'**/{ext}')
                for file in files:
                    if 'venv' in str(file) or 'node_modules' in str(file):
                        continue
                    try:
                        content = file.read_text(encoding='utf-8', errors='ignore')
                        # Look for hardcoded values (e.g., api_key = "abc123")
                        if f'{pattern} = "' in content.lower() or f'{pattern}="' in content.lower():
                            # Skip if it's in comments or examples
                            if 'example' not in content.lower() and '.env' not in content.lower():
                                print(f"{Colors.YELLOW}[!] Possible hardcoded {pattern} in {file.relative_to(project_root)}{Colors.END}")
                                found_sensitive = True
                    except:
                        pass
        except:
            pass

    if not found_sensitive:
        check("No hardcoded secrets", True, "- Good practice")

    # 12. Check Python syntax
    print(f"\n{Colors.BLUE}Checking Python syntax...{Colors.END}")
    python_errors = False
    for py_file in project_root.glob('**/*.py'):
        if 'venv' in str(py_file) or '__pycache__' in str(py_file):
            continue
        try:
            subprocess.run(
                [sys.executable, '-m', 'py_compile', str(py_file)],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError:
            print(f"{Colors.RED}[x] Syntax error in {py_file.relative_to(project_root)}{Colors.END}")
            python_errors = True

    if not python_errors:
        check("Python syntax", True, "- All files valid")
    else:
        all_passed = False

    # Summary
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}[+] All checks passed! Ready to commit.{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}[!] Some checks failed. Review warnings above.{Colors.END}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
