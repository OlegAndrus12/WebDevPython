"""Single Responsibility — AFTER: reshaping the payload (`data_adapter`) and rendering the table
(`pretty_view`) are separate functions, so each has exactly one reason to change."""

import requests

def pretty_view(data: list[dict]):
    pattern = "|{:^10}|{:^10}|{:^10}|"
    for el in data:
        currency, *_ = el.keys()
        buy = el.get(currency).get("buy")
        sale = el.get(currency).get("sale")
        print(pattern.format(currency, sale, buy))


def data_adapter(data: dict) -> list[dict]:
    return [
        {
            f"{el.get('ccy')}": {
                "buy": float(el.get("buy")),
                "sale": float(el.get("sale")),
            }
        }
        for el in data
    ]


if __name__ == "__main__":
    response = requests.get(
        "https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=11"
    )
    response.raise_for_status()
    pretty_view(data_adapter(response.json()))
