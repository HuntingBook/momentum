import io
import json
import inspect
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
import pandas as pd
from sqlmodel import select
from app.db import get_session
from app.models import Stock, DailyPrice, ScreeningPreset, PatternResult, BacktestResult, StrategyDefinition, User, DataSyncLog
from app.schemas import DateRangeRequest, DailyDataRequest, PriceRangeRequest, ScreeningRequest, ScreeningExportRequest, ScreeningResponse, PatternScanRequest, BacktestRequest, ExportRequest, PresetRequest, LoginRequest, AuthResponse, LogDeleteRequest
from app.services.data_sync import sync_stock_list, sync_daily, validate_integrity
from app.services.screening import screen_stocks
from app.services.patterns import detect_patterns, PATTERN_NAMES
from app.services.strategies import get_strategy_map
from app.services.backtest import run_backtest
from app.services.cache import cache_get, cache_set
from app.services.auth import verify_password, issue_token, get_token_payload

router = APIRouter(prefix="/api/v1")

def session_dep():
    session = get_session()
    try:
        yield session
    finally:
        session.close()

def auth_dep(authorization: str | None = Header(default=None), session=Depends(session_dep)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.replace("Bearer ", "")
    payload = get_token_payload(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期")
    user = session.exec(select(User).where(User.username == payload["username"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

def admin_dep(user=Depends(auth_dep)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限")
    return user

@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, session=Depends(session_dep)):
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = issue_token(user.username, user.role)
    return {"token": token, "role": user.role}

@router.get("/stocks")
def list_stocks(session=Depends(session_dep)):
    stocks = session.exec(select(Stock)).all()
    return [s.dict() for s in stocks]

@router.get("/stocks/query")
def search_stocks(keyword: str = "", limit: int = 20, offset: int = 0, session=Depends(session_dep)):
    query = select(Stock)
    if keyword:
        # Simple case-insensitive search
        query = query.where(Stock.symbol.contains(keyword) | Stock.name.contains(keyword))
    
    total = len(session.exec(query).all())
    stocks = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": [s.dict() for s in stocks]}

from fastapi import BackgroundTasks

# Simple in-memory progress tracking
SYNC_STATE = {
    "status": "idle", # idle, running, finished, error
    "type": None, # stock_list, daily
    "current": 0,
    "total": 0,
    "message": ""
}

def update_progress(current, total, message=""):
    SYNC_STATE["current"] = current
    SYNC_STATE["total"] = total
    SYNC_STATE["message"] = message

@router.get("/data/sync/progress")
def get_sync_progress():
    return SYNC_STATE

def run_sync_stock_list_task(session):
    global SYNC_STATE
    SYNC_STATE.update({"status": "running", "type": "stock_list", "current": 0, "total": 0, "message": "Starting..."})
    try:
        # Pass a callback or just let sync_stock_list run? 
        # sync_stock_list in data_sync.py is monolithic. We should probably modify it to yield progress or just set "running".
        # For stock list, it's usually "Fetch A, Fetch B, Merge". We can just mock progress steps.
        # But better: modify sync_stock_list to accept a callback.
        count = sync_stock_list(session, progress_callback=update_progress)
        SYNC_STATE.update({"status": "finished", "current": count, "total": count, "message": f"Completed. Synced {count} stocks."})
    except Exception as e:
        SYNC_STATE.update({"status": "error", "message": str(e)})

def run_sync_daily_task(session, symbols, start_date, end_date, sync_type):
    global SYNC_STATE
    SYNC_STATE.update({"status": "running", "type": "daily", "current": 0, "total": len(symbols), "message": "Starting..."})
    try:
        # sync_daily in data_sync.py loops through symbols. Let's pass callback.
        count = sync_daily(session, symbols, start_date, end_date, sync_type, progress_callback=update_progress)
        SYNC_STATE.update({"status": "finished", "current": len(symbols), "total": len(symbols), "message": f"Completed. Synced {count} records."})
    except Exception as e:
        SYNC_STATE.update({"status": "error", "message": str(e)})

@router.post("/data/sync/stocks")
def sync_stocks(background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(admin_dep)):
    if SYNC_STATE["status"] == "running":
        raise HTTPException(status_code=400, detail="Task already running")
    background_tasks.add_task(run_sync_stock_list_task, session)
    return {"status": "started", "message": "Stock sync started in background"}

@router.post("/data/sync/daily")
def sync_daily_data(payload: DateRangeRequest, background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(admin_dep)):
    if SYNC_STATE["status"] == "running":
        raise HTTPException(status_code=400, detail="Task already running")
    
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    if not symbols:
        raise HTTPException(status_code=400, detail="无可同步股票")
    
    background_tasks.add_task(run_sync_daily_task, session, symbols, payload.start_date, payload.end_date, payload.sync_type)
    return {"status": "started", "count": len(symbols)}

@router.post("/data/daily")
def get_daily_data(payload: DailyDataRequest, session=Depends(session_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    if not symbols:
        return []
    stocks = session.exec(select(Stock).where(Stock.symbol.in_(symbols))).all()
    ids = [s.id for s in stocks]
    prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id.in_(ids), DailyPrice.trade_date == payload.trade_date)).all()
    return [p.dict() for p in prices]

@router.post("/data/price_range")
def get_price_range(payload: PriceRangeRequest, session=Depends(session_dep)):
    stock = session.exec(select(Stock).where(Stock.symbol == payload.symbol)).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= payload.start_date, DailyPrice.trade_date <= payload.end_date).order_by(DailyPrice.trade_date)).all()
    
    
    if not prices:
        return []

    if payload.frequency == "D":
        return [p.dict() for p in prices]

    # Resampling for Weekly/Monthly
    df = pd.DataFrame([p.dict() for p in prices])
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df.set_index('trade_date', inplace=True)
    
    rule = 'W' if payload.frequency == 'W' else 'M'
    resampled = df.resample(rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # Format back to list of dicts with date string
    results = []
    for date, row in resampled.iterrows():
        results.append({
            "trade_date": date.strftime('%Y-%m-%d'),
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
            "volume": row['volume']
        })
    return results

@router.post("/data/integrity")
def check_integrity(payload: DateRangeRequest, session=Depends(session_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    return [validate_integrity(session, symbol, payload.start_date, payload.end_date) for symbol in symbols]

@router.post("/screening/run", response_model=ScreeningResponse)
def run_screening(payload: ScreeningRequest, session=Depends(session_dep)):
    cache_key = f"screen:{json.dumps(payload.dict(), ensure_ascii=False)}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    items = screen_stocks(session, payload.dict())
    response = {"total": len(items), "items": items}
    cache_set(cache_key, response, ttl=120)
    return response

@router.post("/screening/export")
def export_screening(payload: ScreeningExportRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    items = screen_stocks(session, payload.dict())
    df = pd.DataFrame(items)
    if payload.file_type == "xlsx":
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=screening.xlsx"})
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=screening.csv"})

@router.post("/screening/preset")
def save_preset(payload: PresetRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    preset = session.exec(select(ScreeningPreset).where(ScreeningPreset.name == payload.name)).first()
    if preset:
        preset.payload_json = json.dumps(payload.payload, ensure_ascii=False)
    else:
        preset = ScreeningPreset(name=payload.name, payload_json=json.dumps(payload.payload, ensure_ascii=False))
        session.add(preset)
    session.commit()
    return {"status": "ok"}

@router.get("/screening/preset")
def list_presets(session=Depends(session_dep)):
    presets = session.exec(select(ScreeningPreset)).all()
    return [{"name": p.name, "payload": json.loads(p.payload_json)} for p in presets]

@router.delete("/screening/preset")
def delete_preset(name: str, session=Depends(session_dep), user=Depends(auth_dep)):
    preset = session.exec(select(ScreeningPreset).where(ScreeningPreset.name == name)).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    session.delete(preset)
    session.commit()
    return {"status": "ok"}

@router.post("/patterns/scan")
def scan_patterns(payload: PatternScanRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    results = []
    for symbol in symbols:
        stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
        if not stock:
            continue
        prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= payload.start_date, DailyPrice.trade_date <= payload.end_date)).all()
        if not prices:
            continue
        df = pd.DataFrame([p.dict() for p in prices])
        if df.empty:
            continue
        patterns = detect_patterns(df.sort_values("trade_date"), payload.patterns, payload.params)
        if not patterns:
            continue
        for item in patterns:
            session.add(PatternResult(symbol=symbol, pattern_name=item["pattern_name"], detected_date=item["detected_date"], success_rate=item["success_rate"], score=item["score"]))
        results.append({"symbol": symbol, "name": stock.name, "patterns": patterns})
    session.commit()
    return results

@router.get("/patterns/library")
def list_patterns():
    return PATTERN_NAMES

@router.get("/dashboard/stats")
def get_dashboard_stats(session=Depends(session_dep)):
    stock_count = len(session.exec(select(Stock)).all())
    # Mocking other stats for now as we don't have tables for them yet
    return {
        "stock_count": stock_count,
        "backtest_count": len(session.exec(select(BacktestResult)).all()),
        "screening_count": len(session.exec(select(ScreeningPreset)).all()),
        "data_status": "稳定"
    }

@router.get("/dashboard/tasks")
def get_dashboard_tasks(session=Depends(session_dep)):
    today = date.today()
    
    # Check if sync happened today
    sync_log = session.exec(select(DataSyncLog).where(DataSyncLog.created_at >= today, DataSyncLog.data_source == "akshare").limit(1)).first()
    sync_done = sync_log is not None
    
    # Check if any backtest ran today
    backtest_log = session.exec(select(BacktestResult).where(BacktestResult.created_at >= today).limit(1)).first()
    backtest_done = backtest_log is not None
    
    tasks = [
        {"id": 1, "text": "完成全市场增量数据同步", "completed": sync_done},
        {"id": 2, "text": "执行每日策略回测验证", "completed": backtest_done},
        {"id": 3, "text": "导出最新选股结果清单", "completed": False} # Logic for export check is harder, keep as manual reminder or check logs
    ]
    return tasks

@router.get("/dashboard/market_cap")
def get_market_cap_distribution(session=Depends(session_dep)):
    # Only include stocks with valid market_cap data
    stocks = session.exec(
        select(Stock)
        .where(Stock.market_cap != None)
        .where(Stock.market_cap > 0)
        .order_by(Stock.market_cap.desc())
        .limit(6)
    ).all()
    data = []
    for s in stocks:
        data.append({"name": s.name, "value": s.market_cap, "symbol": s.symbol})
    return data

@router.get("/strategies")
def list_strategies(session=Depends(session_dep)):
    strategies = session.exec(select(StrategyDefinition)).all()
    if not strategies:
        return [{"name": name, "description": f"{name}策略"} for name in get_strategy_map().keys()]
    return [s.dict() for s in strategies]

@router.post("/backtest/run")
def run_strategy_backtest(payload: BacktestRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    strategy_map = get_strategy_map()
    if payload.strategy_name not in strategy_map:
        raise HTTPException(status_code=400, detail="策略不存在")
    results = []
    for symbol in payload.symbols:
        stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
        if not stock:
            continue
        prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= payload.start_date, DailyPrice.trade_date <= payload.end_date)).all()
        if not prices:
            continue
        df = pd.DataFrame([p.dict() for p in prices])
        if df.empty:
            continue
        df = df.sort_values("trade_date")
        strategy_func = strategy_map[payload.strategy_name]
        allowed_params = {k: v for k, v in payload.parameters.items() if k in inspect.signature(strategy_func).parameters}
        signal = strategy_func(df, **allowed_params)
        result = run_backtest(df, signal)
        metrics = result["metrics"]
        session.add(BacktestResult(
            strategy_name=payload.strategy_name,
            symbol=symbol,
            start_date=payload.start_date,
            end_date=payload.end_date,
            annual_return=metrics["annual_return"],
            max_drawdown=metrics["max_drawdown"],
            sharpe=metrics["sharpe"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
        ))
        results.append({"symbol": symbol, **metrics, "equity_curve": result["equity_curve"], "dates": result["dates"]})
    session.commit()
    return results

@router.post("/export")
def export_data(payload: ExportRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    stocks = session.exec(select(Stock).where(Stock.symbol.in_(symbols))).all()
    # Optimization: If no date range provided, default to last 30 days to avoid full DB dump
    if not payload.start_date and not payload.end_date:
        payload.start_date = date.today() - timedelta(days=30)
    
    ids = [s.id for s in stocks]
    query = select(DailyPrice).where(DailyPrice.stock_id.in_(ids))
    if payload.start_date:
        query = query.where(DailyPrice.trade_date >= payload.start_date)
    if payload.end_date:
        query = query.where(DailyPrice.trade_date <= payload.end_date)
    prices = session.exec(query).all()
    df = pd.DataFrame([p.dict() for p in prices]) if prices else pd.DataFrame()
    if payload.file_type == "xlsx":
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=export.xlsx"})
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=export.csv"})

@router.get("/system/logs")
@router.get("/system/logs")
def get_system_logs(session=Depends(session_dep), limit: int = 100, offset: int = 0):
    query = select(DataSyncLog).order_by(DataSyncLog.created_at.desc())
    total = len(session.exec(query).all())
    logs = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": logs}

@router.delete("/system/logs")
def delete_system_logs(payload: LogDeleteRequest, session=Depends(session_dep), user=Depends(admin_dep)):
    query = select(DataSyncLog)
    if not payload.delete_all:
        if payload.start_date:
            query = query.where(DataSyncLog.created_at >= payload.start_date)
        if payload.end_date:
            # Add one day to include the end date
            query = query.where(DataSyncLog.created_at < payload.end_date + pd.Timedelta(days=1))
    
    logs = session.exec(query).all()
    count = len(logs)
    for log in logs:
        session.delete(log)
    session.commit()
    return {"status": "ok", "deleted": count}
