from typing import Any


TOLERANCE = 1e-5


def validate_schedule(
    scenario: Any,
    directives: list[dict[str, Any]],
    hourly_plan: list[dict[str, Any]],
) -> None:

    if len(hourly_plan) != 24:
        raise ValueError(
            "hourly_plan must contain 24 entries"
        )

    hours = [
        row["hour"]
        for row in hourly_plan
    ]

    if sorted(hours) != list(range(24)):
        raise ValueError(
            "hourly_plan must contain hours 0 through 23"
        )

    battery = scenario.battery

    # ---------------------------------------------------------
    # Build directive constraints
    # ---------------------------------------------------------

    solar_factor = {
        h: 1.0 for h in range(24)
    }

    reserves = {
        h: battery.minimum_energy_kwh
        for h in range(24)
    }

    no_charge = set()
    no_discharge = set()
    grid_caps = {}

    for directive in directives:

        if not directive["applies"]:
            continue

        dtype = directive["directive_type"]
        adjustment = directive["structured_adjustment"]

        if dtype == "solar_reduction":

            factor = float(
                adjustment["factor"]
            )

            for h in adjustment["hours"]:
                solar_factor[h] = min(
                    solar_factor[h],
                    factor,
                )

        elif dtype == "minimum_battery_reserve":

            value = float(
                adjustment["minimum_energy_kwh"]
            )

            for h in adjustment["hours"]:
                reserves[h] = max(
                    reserves[h],
                    value,
                )

        elif dtype == "no_charge_window":

            no_charge.update(
                adjustment["hours"]
            )

        elif dtype == "no_discharge_window":

            no_discharge.update(
                adjustment["hours"]
            )

        elif dtype == "max_grid_window":

            value = float(
                adjustment["max_grid_kwh"]
            )

            for h in adjustment["hours"]:

                if h in grid_caps:
                    grid_caps[h] = min(
                        grid_caps[h],
                        value,
                    )
                else:
                    grid_caps[h] = value

    # ---------------------------------------------------------
    # Replay schedule
    # ---------------------------------------------------------

    previous_energy = (
        battery.initial_energy_kwh
    )

    for row in hourly_plan:

        h = row["hour"]

        scenario_hour = next(
            item
            for item in scenario.hours
            if item.hour == h
        )

        grid = float(
            row["grid_kwh"]
        )

        solar_used = float(
            row["solar_used_kwh"]
        )

        battery_kwh = float(
            row["battery_kwh"]
        )

        energy_after = float(
            row["battery_energy_after_kwh"]
        )

        action = row["battery_action"]

        # -----------------------------------------------------
        # Basic checks
        # -----------------------------------------------------

        if grid < -TOLERANCE:
            raise ValueError(
                f"Negative grid energy at hour {h}"
            )

        if solar_used < -TOLERANCE:
            raise ValueError(
                f"Negative solar usage at hour {h}"
            )

        if battery_kwh < -TOLERANCE:
            raise ValueError(
                f"Negative battery amount at hour {h}"
            )

        # -----------------------------------------------------
        # Solar availability
        # -----------------------------------------------------

        effective_solar = (
            scenario_hour.solar_kwh
            * solar_factor[h]
        )

        if solar_used > (
            effective_solar + TOLERANCE
        ):
            raise ValueError(
                f"Solar usage exceeds available "
                f"solar at hour {h}"
            )

        # -----------------------------------------------------
        # Battery action
        # -----------------------------------------------------

        charge = 0.0
        discharge = 0.0

        if action == "charge":

            charge = battery_kwh

            if charge > (
                battery.max_charge_kwh_per_hour
                + TOLERANCE
            ):
                raise ValueError(
                    f"Charge limit exceeded at hour {h}"
                )

        elif action == "discharge":

            discharge = battery_kwh

            if discharge > (
                battery.max_discharge_kwh_per_hour
                + TOLERANCE
            ):
                raise ValueError(
                    f"Discharge limit exceeded at hour {h}"
                )

        elif action == "idle":

            if abs(battery_kwh) > TOLERANCE:
                raise ValueError(
                    f"Idle action must have zero "
                    f"battery amount at hour {h}"
                )

        else:

            raise ValueError(
                f"Invalid battery action at hour {h}"
            )

        # -----------------------------------------------------
        # Operator directives
        # -----------------------------------------------------

        if h in no_charge:

            if charge > TOLERANCE:
                raise ValueError(
                    f"Charging prohibited at hour {h}"
                )

        if h in no_discharge:

            if discharge > TOLERANCE:
                raise ValueError(
                    f"Discharging prohibited at hour {h}"
                )

        if h in grid_caps:

            if grid > (
                grid_caps[h] + TOLERANCE
            ):
                raise ValueError(
                    f"Grid cap exceeded at hour {h}"
                )

        # -----------------------------------------------------
        # Battery transition
        # -----------------------------------------------------

        expected_energy = (
            previous_energy
            + charge
            - discharge
        )

        if abs(
            expected_energy
            - energy_after
        ) > TOLERANCE:

            raise ValueError(
                f"Battery transition invalid "
                f"at hour {h}: "
                f"expected {expected_energy}, "
                f"received {energy_after}"
            )

        # -----------------------------------------------------
        # Battery bounds
        # -----------------------------------------------------

        if energy_after < (
            reserves[h] - TOLERANCE
        ):
            raise ValueError(
                f"Battery reserve violated "
                f"at hour {h}"
            )

        if energy_after > (
            battery.capacity_kwh + TOLERANCE
        ):
            raise ValueError(
                f"Battery capacity exceeded "
                f"at hour {h}"
            )

        # -----------------------------------------------------
        # Energy balance
        # -----------------------------------------------------

        lhs = (
            grid
            + solar_used
            + discharge
        )

        rhs = (
            scenario_hour.demand_kwh
            + charge
        )

        if abs(lhs - rhs) > TOLERANCE:

            raise ValueError(
                f"Energy balance violated "
                f"at hour {h}: "
                f"left={lhs}, right={rhs}"
            )

        previous_energy = energy_after

    # ---------------------------------------------------------
    # End-of-day neutrality
    # ---------------------------------------------------------

    if abs(
        previous_energy
        - battery.initial_energy_kwh
    ) > TOLERANCE:

        raise ValueError(
            "End-of-day battery neutrality violated"
        )
