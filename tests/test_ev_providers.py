from custom_components.mobility_forecast.ev.geocoding import coordinates, parse_address


def test_pdok_exact_postcode_number_and_order():
    payload = {
        "response": {
            "docs": [
                {
                    "type": "adres",
                    "postcode": "1234AB",
                    "huisnummer": 12,
                    "centroide_ll": "POINT(5.1 52.1)",
                }
            ]
        }
    }
    assert parse_address(payload, "Straat 12, 1234 AB Stad") == (52.1, 5.1)
    assert parse_address(payload, "Straat 13, 1234 AB Stad") is None
    assert parse_address(payload, "Stad") is None
    payload["response"]["docs"].append(
        {
            "type": "adres",
            "postcode": "1234AB",
            "huisnummer": 12,
            "centroide_ll": "POINT(5.2 52.2)",
        }
    )
    assert parse_address(payload, "Straat 12, 1234AB Stad") is None
    assert coordinates("52.1, 5.1") == (52.1, 5.1)
