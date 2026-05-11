"""
reset_state.py - One-time script to reset persistent disk for Option C launch

WHY: When deploying v6.0 (Option C), we want a fresh experiment:
  - Old strategy/asset history is no longer relevant
  - £5000 starting balance, not £663 from old crypto bot
  - Clean trade log for the new strategies

WHAT THIS DOES:
  1. Backs up existing /data/trades.json -> /data/trades_v5_backup.json
  2. Backs up existing /data/equity.json -> /data/equity_v5_backup.json
  3. Writes fresh /data/trades.json (empty list)
  4. Writes fresh /data/equity.json with £5000 balance

HOW TO RUN:
  In Render Shell:
    python reset_state.py

  Or manually edit the files in /data on the persistent disk.

SAFETY:
  - Only run ONCE before first v6.0 deploy
  - Idempotent: if already reset, won't re-reset (checks balance)
  - Always backs up before resetting
"""
import os
import json
import sys
import shutil
from datetime import datetime, timezone

DATA_DIR = os.environ.get('DATA_DIR', '/data')
NEW_BALANCE = 5000.0

trades_path = os.path.join(DATA_DIR, 'trades.json')
equity_path = os.path.join(DATA_DIR, 'equity.json')

# Check current state
if os.path.exists(equity_path):
    with open(equity_path) as f:
        eq = json.load(f)
    print(f"Current state:")
    print(f"  Balance: £{eq.get('balance', '?')}")
    print(f"  Starting: £{eq.get('starting_balance', '?')}")
    if abs(eq.get('balance', 0) - NEW_BALANCE) < 1 and eq.get('starting_balance') == NEW_BALANCE:
        print(f"\nAlready reset to £{NEW_BALANCE}. Nothing to do.")
        sys.exit(0)
else:
    print("No equity.json found - clean disk")

# Confirm
print(f"\nThis will:")
print(f"  - Back up existing trades.json -> trades_v5_backup.json")
print(f"  - Back up existing equity.json -> equity_v5_backup.json")
print(f"  - Reset balance to £{NEW_BALANCE}")
print(f"  - Reset trade history to empty")
response = input("\nProceed? (yes/no): ").strip().lower()
if response != 'yes':
    print("Aborted.")
    sys.exit(0)

# Backup
backup_suffix = datetime.now(timezone.utc).strftime('_v5_backup_%Y%m%d_%H%M%S')
if os.path.exists(trades_path):
    shutil.copy(trades_path, trades_path.replace('.json', f'{backup_suffix}.json'))
    print(f"  Backed up trades.json")
if os.path.exists(equity_path):
    shutil.copy(equity_path, equity_path.replace('.json', f'{backup_suffix}.json'))
    print(f"  Backed up equity.json")

# Reset
os.makedirs(DATA_DIR, exist_ok=True)
with open(trades_path, 'w') as f:
    json.dump([], f)
with open(equity_path, 'w') as f:
    json.dump({
        'balance': NEW_BALANCE,
        'starting_balance': NEW_BALANCE,
        'last_updated': datetime.now(timezone.utc).isoformat(),
    }, f, indent=2)

print(f"\n✓ Reset complete.")
print(f"  Trade log: empty")
print(f"  Balance: £{NEW_BALANCE}")
print(f"  Backups saved with suffix {backup_suffix}")
