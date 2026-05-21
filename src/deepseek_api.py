import requests
from datetime import date
from .usage_snapshot import UsageSnapshot, ModelUsage

PLATFORM_BASE = "https://platform.deepseek.com"

HEADERS_TEMPLATE = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://platform.deepseek.com",
    "Referer": "https://platform.deepseek.com/usage",
}


class DeepSeekAPIError(Exception):
    pass


def _get(user_token: str, path: str, params: dict = None) -> dict:
    headers = {**HEADERS_TEMPLATE, "Authorization": f"Bearer {user_token}"}
    resp = requests.get(
        f"{PLATFORM_BASE}{path}",
        params=params or {},
        headers=headers,
        timeout=15,
    )
    if resp.status_code != 200:
        raise DeepSeekAPIError(f"API returned {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if data.get("code") != 0:
        raise DeepSeekAPIError(data.get("msg", "Unknown error"))
    return data["data"]["biz_data"]


def _parse_amount_item(item: dict) -> dict:
    result = {}
    for u in item.get("usage", []):
        t = u.get("type", "")
        amt = int(u.get("amount", 0) or 0)
        if t == "PROMPT_CACHE_HIT_TOKEN":
            result["prompt_cache_hit"] = amt
        elif t == "PROMPT_CACHE_MISS_TOKEN":
            result["prompt_cache_miss"] = amt
        elif t == "RESPONSE_TOKEN":
            result["completion"] = amt
        elif t == "REQUEST":
            result["api_calls"] = amt
    return result


def _parse_cost_item(item: dict) -> dict:
    result = {}
    for u in item.get("usage", []):
        t = u.get("type", "")
        amt = float(u.get("amount", 0) or 0)
        if t == "PROMPT_CACHE_HIT_TOKEN":
            result["cost_cache_hit"] = amt
        elif t == "PROMPT_CACHE_MISS_TOKEN":
            result["cost_cache_miss"] = amt
        elif t == "RESPONSE_TOKEN":
            result["cost_completion"] = amt
    return result


def fetch_snapshot(user_token: str) -> UsageSnapshot:
    summary = _get(user_token, "/api/v0/users/get_user_summary")

    today = date.today()
    amount_data = _get(user_token, "/api/v0/usage/amount",
                       {"month": str(today.month), "year": str(today.year)})
    cost_data = _get(user_token, "/api/v0/usage/cost",
                     {"month": str(today.month), "year": str(today.year)})

    # parse wallet balances
    normal_wallets = summary.get("normal_wallets", [])
    bonus_wallets = summary.get("bonus_wallets", [])
    normal_balance = float(normal_wallets[0]["balance"]) if normal_wallets else 0.0
    bonus_balance = float(bonus_wallets[0]["balance"]) if bonus_wallets else 0.0

    # parse monthly cost
    monthly_costs = summary.get("monthly_costs", [])
    monthly_cost = float(monthly_costs[0]["amount"]) if monthly_costs else 0.0

    # build per-model data by merging amount + cost
    models_by_name: dict[str, dict] = {}
    for item in amount_data.get("total", []):
        name = item.get("model", "unknown")
        models_by_name[name] = _parse_amount_item(item)

    # cost_data is a list of currency groups, each with .total[]
    cost_list = cost_data if isinstance(cost_data, list) else []
    for currency_group in cost_list:
        for item in currency_group.get("total", []):
            name = item.get("model", "unknown")
            cost_info = _parse_cost_item(item)
            if name in models_by_name:
                models_by_name[name]["cost"] = (
                    cost_info.get("cost_cache_hit", 0)
                    + cost_info.get("cost_cache_miss", 0)
                    + cost_info.get("cost_completion", 0)
                )

    models = []
    total_prompt = 0
    total_completion = 0
    total_api_calls = 0
    total_cost = 0.0

    for name, data in models_by_name.items():
        m = ModelUsage(
            model_name=name,
            prompt_cache_hit_tokens=data.get("prompt_cache_hit", 0),
            prompt_cache_miss_tokens=data.get("prompt_cache_miss", 0),
            completion_tokens=data.get("completion", 0),
            api_calls=data.get("api_calls", 0),
            cost=data.get("cost", 0.0),
        )
        # skip models with zero usage
        if m.total_tokens == 0 and m.api_calls == 0:
            continue
        models.append(m)
        total_prompt += m.prompt_tokens
        total_completion += m.completion_tokens
        total_api_calls += m.api_calls
        total_cost += m.cost

    return UsageSnapshot(
        total_balance=normal_balance + bonus_balance,
        granted_balance=bonus_balance,
        topped_up_balance=normal_balance,
        is_available=normal_balance > 0,
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        total_tokens=total_prompt + total_completion,
        total_cost=total_cost,
        models=models,
    )


def test_connection(user_token: str) -> tuple[bool, str]:
    try:
        summary = _get(user_token, "/api/v0/users/get_user_summary")
        normal = summary.get("normal_wallets", [])
        balance = float(normal[0]["balance"]) if normal else 0.0
        monthly = summary.get("monthly_token_usage", "0")
        return True, f"连接成功！余额: ¥{balance:.2f} | 月用量: {int(monthly):,} tokens"
    except DeepSeekAPIError as e:
        return False, str(e)
    except Exception as e:
        return False, f"连接失败: {e}"
