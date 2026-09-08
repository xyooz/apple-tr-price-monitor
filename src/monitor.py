from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LATEST_FILE = DATA_DIR / "latest.json"
HISTORY_FILE = DATA_DIR / "history.json"

SEAGM_URL = "https://www.seagm.com/zh/itunes-gift-card-turkey"
FRANKFURTER_URL = "https://api.frankfurter.app/latest?from=USD&to=CNY"
ER_API_URL = "https://open.er-api.com/v6/latest/USD"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fetch_html() -> str:
    response = requests.get(SEAGM_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    if "iTunes Gift Card" not in response.text:
        raise RuntimeError("SEAGM 页面返回内容异常，未找到礼品卡标识")
    return response.text


def parse_products(html: str) -> list[dict[str, float | int | str]]:
    """从页面可见文本提取形如 'iTunes Gift Card 1000 TL TR US$ 22.45' 的商品。"""
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)

    pattern = re.compile(
        r"iTunes\s+Gift\s+Card\s+([\d,]+)\s+TL\s+TR"
        r".{0,180}?US\$\s*([\d,.]+)",
        flags=re.IGNORECASE,
    )

    products: dict[int, dict[str, float | int | str]] = {}
    for face_raw, price_raw in pattern.findall(text):
        face_value = int(face_raw.replace(",", ""))
        price_usd = float(price_raw.replace(",", ""))
        if face_value <= 0 or price_usd <= 0:
            continue
        products[face_value] = {
            "face_value_try": face_value,
            "price_usd": round(price_usd, 4),
            "product_name": f"iTunes Gift Card {face_value} TL TR",
        }

    result = [products[key] for key in sorted(products)]
    if len(result) < 5:
        raise RuntimeError(f"SEAGM 价格解析异常，仅识别到 {len(result)} 个面额")
    return result


def previous_fx_rate() -> float | None:
    latest = read_json(LATEST_FILE, {})
    try:
        value = float(latest["exchange_rate"]["usd_cny"])
        return value if value > 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def fetch_usd_cny() -> tuple[float, str]:
    errors: list[str] = []

    try:
        response = requests.get(FRANKFURTER_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        rate = float(response.json()["rates"]["CNY"])
        if rate > 0:
            return rate, "Frankfurter"
    except Exception as exc:  # noqa: BLE001 - 将失败切到备用数据源
        errors.append(f"Frankfurter: {exc}")

    try:
        response = requests.get(ER_API_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        payload = response.json()
        rate = float(payload["rates"]["CNY"])
        if rate > 0:
            return rate, "open.er-api.com"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"ER API: {exc}")

    old_rate = previous_fx_rate()
    if old_rate:
        return old_rate, "previous_successful_rate"

    raise RuntimeError("USD/CNY 汇率获取失败：" + " | ".join(errors))


def normalize_products(
    products: list[dict[str, float | int | str]], usd_cny: float
) -> list[dict[str, float | int | str]]:
    normalized = []
    for product in products:
        face_value = int(product["face_value_try"])
        price_usd = float(product["price_usd"])
        price_cny = price_usd * usd_cny
        normalized.append(
            {
                **product,
                "price_cny": round(price_cny, 2),
                "cny_per_100_try": round(price_cny / face_value * 100, 3),
            }
        )
    return normalized


def append_history(snapshot: dict[str, Any]) -> None:
    history = read_json(HISTORY_FILE, {"snapshots": []})
    snapshots = history.get("snapshots")
    if not isinstance(snapshots, list):
        snapshots = []

    snapshots.append(
        {
            "checked_at": snapshot["checked_at"],
            "usd_cny": snapshot["exchange_rate"]["usd_cny"],
            "products": [
                {
                    "face_value_try": item["face_value_try"],
                    "price_usd": item["price_usd"],
                    "price_cny": item["price_cny"],
                    "cny_per_100_try": item["cny_per_100_try"],
                }
                for item in snapshot["products"]
            ],
        }
    )

    # 页面只需要 30 天趋势，多保留一倍窗口便于后续统计，同时控制仓库体积。
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    retained = []
    for item in snapshots:
        try:
            dt = datetime.fromisoformat(str(item["checked_at"]).replace("Z", "+00:00"))
            if dt >= cutoff:
                retained.append(item)
        except (KeyError, TypeError, ValueError):
            continue

    write_json(
        HISTORY_FILE,
        {
            "retention_days": 60,
            "snapshots": retained,
        },
    )


def main() -> None:
    html = fetch_html()
    raw_products = parse_products(html)
    usd_cny, fx_source = fetch_usd_cny()
    products = normalize_products(raw_products, usd_cny)

    checked_at = now_iso()
    latest = {
        "status": "ok",
        "checked_at": checked_at,
        "source": {
            "name": "SEAGM",
            "url": SEAGM_URL,
            "region": "TR",
        },
        "exchange_rate": {
            "usd_cny": round(usd_cny, 6),
            "source": fx_source,
        },
        "payment": {
            "alipay": {
                "documented_support": True,
                "note": "支付宝可用性及实际手续费以 SEAGM 结算页为准",
            }
        },
        "products": products,
    }

    write_json(LATEST_FILE, latest)
    append_history(latest)

    best = min(products, key=lambda item: float(item["cny_per_100_try"]))
    print(f"抓取成功：{len(products)} 个面额")
    print(f"USD/CNY: {usd_cny:.4f} ({fx_source})")
    print(
        "当前单位成本最低："
        f"{best['face_value_try']} TRY / ¥{best['cny_per_100_try']} per 100 TRY"
    )


if __name__ == "__main__":
    main()
