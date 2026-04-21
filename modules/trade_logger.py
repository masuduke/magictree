"""
trade_logger.py
---------------
Persists trades and equity curve to JSON files.
Provides stats for content generation.
"""
import json
import os
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


def _load(path: str, default) -> any:
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return default


def _save(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


# ── public API ────────────────────────────────────────────────────────────────

def save_trade(trade: dict, cfg) -> None:
    trades = _load(cfg.DATA_FILE, [])
    # Replace if same ID, else append
    trades = [t for t in trades if t.get('id') != trade['id']]
    trades.append(trade)
    _save(cfg.DATA_FILE, trades)


def save_trades(trades: list, cfg) -> None:
    _save(cfg.DATA_FILE, trades)


def load_trades(cfg) -> list:
    return _load(cfg.DATA_FILE, [])


def get_open_trades(cfg) -> list:
    return [t for t in load_trades(cfg) if t.get('status') == 'OPEN']


def update_equity(pnl: float, cfg) -> float:
    """Adds pnl to running equity. Returns new balance."""
    eq = _load(cfg.EQUITY_FILE, {'balance': cfg.INITIAL_CAPITAL, 'history': []})
    eq['balance'] = round(eq['balance'] + pnl, 2)
    eq['history'].append({'date': date.today().isoformat(), 'balance': eq['balance'], 'pnl': pnl})
    _save(cfg.EQUITY_FILE, eq)
    return eq['balance']


def get_equity(cfg) -> dict:
    return _load(cfg.EQUITY_FILE, {'balance': cfg.INITIAL_CAPITAL, 'history': []})


def get_stats(cfg) -> dict:
    """Returns summary statistics for content generation."""
    trades  = load_trades(cfg)
    closed  = [t for t in trades if t.get('status') == 'CLOSED']
    wins    = [t for t in closed if t.get('result') == 'WIN']
    losses  = [t for t in closed if t.get('result') == 'LOSS']
    equity  = get_equity(cfg)
    balance = equity['balance']
    history = equity.get('history', [])

    total_pnl   = sum(t.get('pnl', 0) for t in closed)
    win_rate    = round(len(wins) / len(closed) * 100, 1) if closed else 0
    best_trade  = max(closed, key=lambda t: t.get('pnl', 0), default=None)
    worst_trade = min(closed, key=lambda t: t.get('pnl', 0), default=None)

    # Days active
    if closed:
        first = datetime.fromisoformat(closed[0]['entry_time'])
        days_active = (datetime.utcnow() - first).days + 1
    else:
        days_active = 0

    return {
        'balance':       balance,
        'initial':       cfg.INITIAL_CAPITAL,
        'total_pnl':     round(total_pnl, 2),
        'total_return':  round((balance - cfg.INITIAL_CAPITAL) / cfg.INITIAL_CAPITAL * 100, 2),
        'total_trades':  len(closed),
        'wins':          len(wins),
        'losses':        len(losses),
        'win_rate':      win_rate,
        'days_active':   days_active,
        'best_trade':    best_trade,
        'worst_trade':   worst_trade,
        'open_trades':   len([t for t in trades if t.get('status') == 'OPEN']),
        'equity_history': history,
        'recent_trades': closed[-5:] if closed else [],  # last 5
    }


def count_today_trades(cfg) -> int:
    today  = date.today().isoformat()
    trades = load_trades(cfg)
    return sum(1 for t in trades if t.get('entry_time', '').startswith(today)
               and t.get('status') in ('OPEN', 'CLOSED'))
