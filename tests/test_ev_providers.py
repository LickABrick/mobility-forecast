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


def test_ndw_verified_schema_fail_closed_units_and_radius():
    from datetime import UTC, datetime

    from custom_components.mobility_forecast.ev.charge_points import parse_points

    now = datetime.now(UTC)
    row = {
        "type": "Feature",
        "id": "public",
        "geometry": {"type": "Point", "coordinates": [5, 52]},
        "properties": {
            "open": True,
            "last_updated": now.isoformat(),
            "availabilities": [
                {
                    "available": 1,
                    "total": 2,
                    "connector_type": "IEC_62196_T2",
                    "power_type": "AC3",
                    "power_max": 11,
                }
            ],
        },
    }
    payload = {"type": "FeatureCollection", "features": [row]}
    assert parse_points(payload, 52, 5, 300, now)[0].ac_power_kw == 11
    row["properties"]["availabilities"][0]["power_max"] = 15000
    assert not parse_points(payload, 52, 5, 300, now)
    row["properties"]["availabilities"][0]["power_max"] = 11
    assert not parse_points(payload, 53, 5, 300, now)
    row["properties"]["open"] = False
    assert not parse_points(payload, 52, 5, 300, now)
