import requests


url = "http://127.0.0.1:8000/optimize-energy"


data = {
    "scenario_id": "test-001",
    "operator_notes": [
        "Do not charge the battery from 14:00 to 16:00."
    ],
    "battery": {
        "capacity_kwh": 10,
        "initial_energy_kwh": 5,
        "minimum_energy_kwh": 2,
        "max_charge_kwh_per_hour": 3,
        "max_discharge_kwh_per_hour": 3
    },
    "hours": [
        {"hour": 0, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 1, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 2, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 3, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 4, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 5, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 6, "demand_kwh": 2, "solar_kwh": 1, "tariff_bdt_per_kwh": 10},
        {"hour": 7, "demand_kwh": 2, "solar_kwh": 2, "tariff_bdt_per_kwh": 10},
        {"hour": 8, "demand_kwh": 2, "solar_kwh": 3, "tariff_bdt_per_kwh": 10},
        {"hour": 9, "demand_kwh": 2, "solar_kwh": 3, "tariff_bdt_per_kwh": 10},
        {"hour": 10, "demand_kwh": 2, "solar_kwh": 3, "tariff_bdt_per_kwh": 10},
        {"hour": 11, "demand_kwh": 2, "solar_kwh": 3, "tariff_bdt_per_kwh": 10},
        {"hour": 12, "demand_kwh": 2, "solar_kwh": 2, "tariff_bdt_per_kwh": 10},
        {"hour": 13, "demand_kwh": 2, "solar_kwh": 2, "tariff_bdt_per_kwh": 10},
        {"hour": 14, "demand_kwh": 2, "solar_kwh": 1, "tariff_bdt_per_kwh": 10},
        {"hour": 15, "demand_kwh": 2, "solar_kwh": 1, "tariff_bdt_per_kwh": 10},
        {"hour": 16, "demand_kwh": 2, "solar_kwh": 1, "tariff_bdt_per_kwh": 10},
        {"hour": 17, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 18, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 19, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 20, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 21, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 22, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
        {"hour": 23, "demand_kwh": 2, "solar_kwh": 0, "tariff_bdt_per_kwh": 10}
    ]
}


print("Sending optimization request...")

try:
    response = requests.post(
        url,
        json=data,
        timeout=120
    )

    print("\nSTATUS CODE:")
    print(response.status_code)

    print("\nRESPONSE:")
    print(response.text)

except requests.exceptions.Timeout:
    print("\nERROR: Request timed out.")

except requests.exceptions.ConnectionError:
    print("\nERROR: Could not connect to FastAPI.")
    print("Make sure the server is running.")

except Exception as exc:
    print("\nERROR:")
    print(repr(exc))
