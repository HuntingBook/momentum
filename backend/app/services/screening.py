from datetime import date
from typing import Dict, Any, List
import pandas as pd
from sqlmodel import select
from app.models import Stock, DailyPrice, FactorValue
from app.services.indicators import rsi, macd, kdj

def _latest_factor_map(factors: pd.DataFrame) -> pd.DataFrame:
    if factors.empty:
        return factors
    return factors.sort_values("factor_date").groupby("stock_id").tail(1)

def _latest_price_map(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return prices
    return prices.sort_values("trade_date").groupby("stock_id").tail(1)

def _apply_range(df: pd.DataFrame, column: str, min_val, max_val):
    if min_val is not None:
        df = df[df[column] >= min_val]
    if max_val is not None:
        df = df[df[column] <= max_val]
    return df

def screen_stocks(session, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    stocks = session.exec(select(Stock)).all()
    if not stocks:
        return []
    
    # Explicitly build dict to ensure 'id' is present and not relying on model_dump defaults
    stock_data = []
    for s in stocks:
        stock_data.append({
            "id": s.id,
            "symbol": s.symbol,
            "name": s.name,
            "market": s.market,
            "industry": s.industry,
            "market_cap": s.market_cap,
            "pe_ratio": s.pe_ratio,
            "pb_ratio": s.pb_ratio
        })
    stock_df = pd.DataFrame(stock_data)

    # Optimization: Fetch only necessary price/factor columns to reduce memory
    # Only fetch last 30 days of data to find the latest
    from datetime import timedelta
    cutoff_date = date.today() - timedelta(days=30)

    prices = session.exec(select(DailyPrice).where(DailyPrice.trade_date >= cutoff_date)).all()
    if prices:
        price_df = pd.DataFrame([p.dict() for p in prices])
        if "id" in price_df.columns:
            price_df = price_df.drop(columns=["id"])
        price_latest = _latest_price_map(price_df)
    else:
        # Create empty DF with expected columns to avoid merge error
        price_latest = pd.DataFrame(columns=["stock_id", "close", "trade_date"])

    factors = session.exec(select(FactorValue).where(FactorValue.factor_date >= cutoff_date)).all()
    if factors:
        factor_df = pd.DataFrame([f.dict() for f in factors])
        if "id" in factor_df.columns:
            factor_df = factor_df.drop(columns=["id"])
        factor_latest = _latest_factor_map(factor_df)
    else:
        factor_latest = pd.DataFrame(columns=["stock_id", "momentum", "volatility", "liquidity"])

    # Merge logic
    # Ensure id columns type match (int)
    if "id" in stock_df.columns:
        stock_df["id"] = stock_df["id"].astype(int)
    
    # Check if right DFs have the key
    if "stock_id" not in price_latest.columns:
        price_latest["stock_id"] = pd.Series(dtype='int')
    if "stock_id" not in factor_latest.columns:
        factor_latest["stock_id"] = pd.Series(dtype='int')

    merged = stock_df.merge(price_latest, left_on="id", right_on="stock_id", how="left") \
                     .merge(factor_latest, left_on="id", right_on="stock_id", how="left", suffixes=("", "_factor"))
    basic = criteria.get("basic_filters", {})
    merged = _apply_range(merged, "market_cap", basic.get("market_cap_min"), basic.get("market_cap_max"))
    merged = _apply_range(merged, "pe_ratio", basic.get("pe_min"), basic.get("pe_max"))
    merged = _apply_range(merged, "pb_ratio", basic.get("pb_min"), basic.get("pb_max"))
    tech = criteria.get("technical_filters", {})
    if "rsi_min" in tech or "rsi_max" in tech:
        merged["rsi"] = rsi(merged["close"].fillna(0))
        merged = _apply_range(merged, "rsi", tech.get("rsi_min"), tech.get("rsi_max"))
    if tech.get("macd_positive"):
        macd_line, signal_line, _ = macd(merged["close"].fillna(0))
        merged = merged[macd_line > signal_line]
    if tech.get("kdj_positive"):
        k, d, j = kdj(merged.fillna(0))
        merged = merged[k > d]
    factor = criteria.get("factor_filters", {})
    merged = _apply_range(merged, "momentum", factor.get("momentum_min"), factor.get("momentum_max"))
    merged = _apply_range(merged, "volatility", factor.get("volatility_min"), factor.get("volatility_max"))
    merged = _apply_range(merged, "liquidity", factor.get("liquidity_min"), factor.get("liquidity_max"))
    for custom in criteria.get("custom_filters", []):
        field = custom.get("field")
        min_val = custom.get("min")
        max_val = custom.get("max")
        if field in merged.columns:
            merged = _apply_range(merged, field, min_val, max_val)
    merged = merged.sort_values("market_cap", ascending=False)
    return merged.head(200).to_dict(orient="records")
