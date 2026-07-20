from fastapi import APIRouter, HTTPException
from app.services.data_service import fetch_price_history
from app.services.pair_analysis import analyze_pair

router = APIRouter(prefix="/api/pairs", tags=["pairs"])


@router.get("/{ticker_a}/{ticker_b}")
def get_pair_detail(ticker_a: str, ticker_b: str, days: int = 500):
    ticker_a, ticker_b = ticker_a.upper(), ticker_b.upper()
    frames = fetch_price_history([ticker_a, ticker_b], days=days)
    if ticker_a not in frames or ticker_b not in frames:
        raise HTTPException(status_code=404, detail="Could not fetch data for one or both tickers")

    df_a = frames[ticker_a].set_index("date")
    df_b = frames[ticker_b].set_index("date")
    pa, pb = df_a["close"].align(df_b["close"], join="inner")

    analysis = analyze_pair(pa, pb)

    return {
        "ticker_a": ticker_a, "ticker_b": ticker_b,
        "dates": [d.strftime("%Y-%m-%d") for d in pa.index],
        "price_a": pa.round(2).tolist(),
        "price_b": pb.round(2).tolist(),
        **analysis,
    }
