from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from .models import EnergyScenario
from .interpreter import interpret_notes_with_llm
from .optimizer import optimize_energy
from .validator import validate_schedule


# Load the Gemini API key from .env
load_dotenv()


app = FastAPI(
    title="BUP GridWise Energy Optimizer"
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/optimize-energy")
def optimize(scenario: EnergyScenario):

    try:
        # Read the 24 hours received from the request.
        received_hours = [
            item.hour for item in scenario.hours
        ]

        # Temporary debugging output.
        print("RECEIVED HOURS:", received_hours)

        # Hours must be exactly 0 through 23.
        if sorted(received_hours) != list(range(24)):
            raise HTTPException(
                status_code=400,
                detail="hours must contain exactly 0 through 23",
            )

        # Interpret operator notes using Gemini.
        directives = interpret_notes_with_llm(
            scenario.operator_notes,
            scenario.battery.capacity_kwh,
        )

        # Create the optimized schedule.
        result = optimize_energy(
            scenario,
            directives,
        )

        # Deterministically validate the final schedule.
        validate_schedule(
            scenario,
            directives,
            result["hourly_plan"],
        )

        return {
            "scenario_id": scenario.scenario_id,
            "directive_interpretation": directives,
            "hourly_plan": result["hourly_plan"],
            "total_grid_kwh": result["total_grid_kwh"],
            "total_cost_bdt": result["total_cost_bdt"],
            "peak_grid_kwh": result["peak_grid_kwh"],
            "plan_summary": (
                "The schedule uses available solar first "
                "and optimizes battery charging and "
                "discharging while satisfying all "
                "validated operator directives and "
                "battery constraints."
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        # Temporary debugging.
        # We will make this generic before final submission.
        print("OPTIMIZATION ERROR:", repr(exc))

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
