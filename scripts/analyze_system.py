#!/usr/bin/env python3
"""
Initial system analysis script
Run during installation to build comprehensive system knowledge
"""


import json
import subprocess
import sys
from pathlib import Path
import sqlite3


def analyze_hyprland():
    """Analyze Hyprland configuration"""
    config_path = Path.home() / '.config/hypr/hyprland.conf'
    
    if not config_path.exists():
        print("⚠️  Hyprland config not found")
        return {}
    
    with open(config_path) as f:
        content = f.read()
    
    # Parse keybindings
    keybinds = []
    for line in content.split('\n'):
        if 'bind' in line and '=' in line:
            keybinds.append(line.strip())
    
    print(f"✓ Found {len(keybinds)} Hyprland keybindings")
    
    return {'keybinds': keybinds, 'raw_config': content[:5000]}


def analyze_shell():
    """Analyze shell configuration"""
    shell_files = [
        Path.home() / '.bashrc',
        Path.home() / '.zshrc',
    ]
    
    configs = {}
    for path in shell_files:
        if path.exists():
            configs[path.name] = path.read_text()[:3000]
            print(f"✓ Analyzed {path.name}")
    
    return configs


def analyze_packages():
    """Get installed package list"""
    try:
        result = subprocess.run(['pacman', '-Q'], capture_output=True, text=True)
        packages = result.stdout.strip().split('\n')
        print(f"✓ Found {len(packages)} installed packages")
        return packages[:500]  # Limit to first 500
    except:
        return []


def main():
    if len(sys.argv) < 3:
        print("Usage: analyze_system.py <config_dir> <db_path>")
        sys.exit(1)
    
    config_dir = Path(sys.argv[1])
    db_path = Path(sys.argv[2])
    
    print("\n🔍 Performing system analysis...\n")
    
    # Gather all data
    data = {
        'hyprland': analyze_hyprland(),
        'shell': analyze_shell(),
        'packages': analyze_packages(),
    }
    
    # Store in database
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute("INSERT OR REPLACE INTO system_state VALUES (?, ?, datetime('now'))",
              ('initial_analysis', json.dumps(data)))
    
    conn.commit()
    conn.close()
    
    print("\n✓ System analysis complete and stored in database\n")


if __name__ == '__main__':
    main()