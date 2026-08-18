"""Single Responsibility — BEFORE: `pretty_view` both reshapes the API payload and prints it, so a
change to the data format and a change to the table layout land in the same function."""

import requests

# https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=11


def pretty_view(data: list[dict]):
    # data preparation
    result = [
        {
            f"{el.get('ccy')}": {
                "buy": float(el.get("buy")),
                "sale": float(el.get("sale")),
            }
        }
        for el in data
    ]
    # will I use it somewhere else?
    # data visualisation
    pattern = "|{:^10}|{:^10}|{:^10}|"
    print(pattern.format("currency", "sale", "buy"))
    for el in result:
        currency, *_ = el.keys()
        buy = el.get(currency).get("buy")
        sale = el.get(currency).get("sale")
        print(pattern.format(currency, sale, buy))


if __name__ == "__main__":

    response = requests.get(
        "https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=11"
    )
    response.raise_for_status()
    data = response.json()
    pretty_view(data)
