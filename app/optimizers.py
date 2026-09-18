from typing import Any

from ortools.linear_solver import pywraplp


TOLERANCE = 1e-6


def optimize_energy(
    scenario: Any,
    directives: list[dict[str, Any]],
) -> dict[str, Any]:

    hours = sorted(
        scenario.hours,
        key=lambda x: x.hour
    )

    battery = scenario.battery

    # ---------------------------------------------------------
    # Directive lookup
    # ---------------------------------------------------------

    solar_factor = {
        h: 1.0 for h in range(24)
    }

    reserve = {
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

            factor = float(adjustment["factor"])

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
                reserve[h] = max(
                    reserve[h],
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
    # Effective solar
    # ---------------------------------------------------------

    effective_solar = {}

    for item in hours:

        h = item.hour

        effective_solar[h] = (
            item.solar_kwh
            * solar_factor[h]
        )

    # ---------------------------------------------------------
    # Solver
    #
    # CBC is used because we need a binary variable to prevent
    # charging and discharging simultaneously.
    # ---------------------------------------------------------

    solver = pywraplp.Solver.CreateSolver("CBC")

    if solver is None:
        raise RuntimeError(
            "Could not create CBC optimizer"
        )

    # ---------------------------------------------------------
    # Variables
    # ---------------------------------------------------------

    grid = {}
    solar = {}
    charge = {}
    discharge = {}
    energy = {}

    # 1 = charging mode
    # 0 = discharging/idle mode
    charge_mode = {}

    for item in hours:

        h = item.hour

        grid[h] = solver.NumVar(
            0.0,
            solver.infinity(),
            f"grid_{h}",
        )

        solar[h] = solver.NumVar(
            0.0,
            effective_solar[h],
            f"solar_{h}",
        )

        charge[h] = solver.NumVar(
            0.0,
            battery.max_charge_kwh_per_hour,
            f"charge_{h}",
        )

        discharge[h] = solver.NumVar(
            0.0,
            battery.max_discharge_kwh_per_hour,
            f"discharge_{h}",
        )

        energy[h] = solver.NumVar(
            0.0,
            battery.capacity_kwh,
            f"energy_{h}",
        )

        charge_mode[h] = solver.BoolVar(
            f"charge_mode_{h}"
        )

    # ---------------------------------------------------------
    # Constraints
    # ---------------------------------------------------------

    for item in hours:

        h = item.hour

        # Energy balance:
        #
        # grid + solar + discharge
        # =
        # demand + charge
        #
        solver.Add(
            grid[h]
            + solar[h]
            + discharge[h]
            == item.demand_kwh + charge[h]
        )

        # -----------------------------------------------------
        # IMPORTANT:
        # Prevent simultaneous charge + discharge.
        # -----------------------------------------------------

        solver.Add(
            charge[h]
            <= battery.max_charge_kwh_per_hour
            * charge_mode[h]
        )

        solver.Add(
            discharge[h]
            <= battery.max_discharge_kwh_per_hour
            * (1 - charge_mode[h])
        )

        # -----------------------------------------------------
        # Battery transition
        # -----------------------------------------------------

        if h == 0:

            solver.Add(
                energy[h]
                == (
                    battery.initial_energy_kwh
                    + charge[h]
                    - discharge[h]
                )
            )

        else:

            solver.Add(
                energy[h]
                == (
                    energy[h - 1]
                    + charge[h]
                    - discharge[h]
                )
            )

        # Battery reserve.
        solver.Add(
            energy[h] >= reserve[h]
        )

        # No charging directive.
        if h in no_charge:

            solver.Add(
                charge[h] == 0
            )

        # No discharging directive.
        if h in no_discharge:

            solver.Add(
                discharge[h] == 0
            )

        # Grid cap.
        if h in grid_caps:

            solver.Add(
                grid[h] <= grid_caps[h]
            )

    # ---------------------------------------------------------
    # End-of-day neutrality
    # ---------------------------------------------------------

    solver.Add(
        energy[23]
        == battery.initial_energy_kwh
    )

    # ---------------------------------------------------------
    # Objective
    # ---------------------------------------------------------

    objective = solver.Objective()

    for item in hours:

        objective.SetCoefficient(
            grid[item.hour],
            item.tariff_bdt_per_kwh,
        )

    objective.SetMinimization()

    # ---------------------------------------------------------
    # Solve
    # ---------------------------------------------------------

    status = solver.Solve()

    if status != pywraplp.Solver.OPTIMAL:

        raise RuntimeError(
            "No optimal energy schedule exists"
        )

    # ---------------------------------------------------------
    # Build result
    # ---------------------------------------------------------

    hourly_plan = []

    for item in hours:

        h = item.hour

        grid_value = grid[h].solution_value()
        solar_value = solar[h].solution_value()
        charge_value = charge[h].solution_value()
        discharge_value = discharge[h].solution_value()
        energy_value = energy[h].solution_value()

        # Remove tiny numerical noise.
        if abs(grid_value) < TOLERANCE:
            grid_value = 0.0

        if abs(solar_value) < TOLERANCE:
            solar_value = 0.0

        if abs(charge_value) < TOLERANCE:
            charge_value = 0.0

        if abs(discharge_value) < TOLERANCE:
            discharge_value = 0.0

        if abs(energy_value) < TOLERANCE:
            energy_value = 0.0

        # -----------------------------------------------------
        # Battery action
        # -----------------------------------------------------

        if charge_value > TOLERANCE:

            action = "charge"
            battery_value = charge_value

        elif discharge_value > TOLERANCE:

            action = "discharge"
            battery_value = discharge_value

        else:

            action = "idle"
            battery_value = 0.0

        hourly_plan.append(
            {
                "hour": h,
                "grid_kwh": max(
                    0.0,
                    grid_value,
                ),
                "solar_used_kwh": max(
                    0.0,
                    solar_value,
                ),
                "battery_action": action,
                "battery_kwh": max(
                    0.0,
                    battery_value,
                ),
                "battery_energy_after_kwh": max(
                    0.0,
                    energy_value,
                ),
            }
        )

    # ---------------------------------------------------------
    # Totals
    # ---------------------------------------------------------

    total_grid = sum(
        row["grid_kwh"]
        for row in hourly_plan
    )

    total_cost = sum(
        row["grid_kwh"]
        * next(
            item.tariff_bdt_per_kwh
            for item in hours
            if item.hour == row["hour"]
        )
        for row in hourly_plan
    )

    peak_grid = max(
        row["grid_kwh"]
        for row in hourly_plan
    )

    return {
        "hourly_plan": hourly_plan,
        "total_grid_kwh": total_grid,
        "total_cost_bdt": total_cost,
        "peak_grid_kwh": peak_grid,
    }
