import json
import os
import math
import time
from typing import Any

from google import genai


ALLOWED_DIRECTIVES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


def validate_directive(
    directive: dict[str, Any],
    note_index: int,
    battery_capacity: float,
) -> dict[str, Any]:

    if not isinstance(directive, dict):
        raise ValueError("Directive must be an object")

    if directive.get("note_index") != note_index:
        raise ValueError("Invalid note_index")

    directive_type = directive.get("directive_type")
    applies = directive.get("applies")
    adjustment = directive.get("structured_adjustment")

    if directive_type not in ALLOWED_DIRECTIVES:
        raise ValueError("Unsupported directive type")

    if directive_type == "no_op":
        if applies is not False:
            raise ValueError("no_op must have applies=false")

        if adjustment is not None:
            raise ValueError(
                "no_op must have null adjustment"
            )

        return directive

    if applies is not True:
        raise ValueError(
            "Applicable directives must have applies=true"
        )

    if not isinstance(adjustment, dict):
        raise ValueError(
            "Missing structured adjustment"
        )

    hours = adjustment.get("hours")

    if not isinstance(hours, list):
        raise ValueError(
            "hours must be a list"
        )

    if len(hours) != len(set(hours)):
        raise ValueError(
            "hours must be unique"
        )

    if any(
        not isinstance(h, int) or isinstance(h, bool)
        for h in hours
    ):
        raise ValueError(
            "hours must contain integers"
        )

    if any(
        h < 0 or h > 23
        for h in hours
    ):
        raise ValueError(
            "hours must be between 0 and 23"
        )

    if hours != sorted(hours):
        raise ValueError(
            "hours must be ascending"
        )

    if directive_type == "solar_reduction":

        factor = adjustment.get("factor")

        if not isinstance(
            factor,
            (int, float)
        ):
            raise ValueError(
                "solar factor must be numeric"
            )

        if not math.isfinite(
            float(factor)
        ):
            raise ValueError(
                "solar factor must be finite"
            )

        if not 0 <= factor <= 1:
            raise ValueError(
                "solar factor must be between 0 and 1"
            )

    elif directive_type == "minimum_battery_reserve":

        reserve = adjustment.get(
            "minimum_energy_kwh"
        )

        if not isinstance(
            reserve,
            (int, float)
        ):
            raise ValueError(
                "reserve must be numeric"
            )

        if not math.isfinite(
            float(reserve)
        ):
            raise ValueError(
                "reserve must be finite"
            )

        if (
            reserve < 0
            or reserve > battery_capacity
        ):
            raise ValueError(
                "invalid battery reserve"
            )

    elif directive_type == "max_grid_window":

        maximum = adjustment.get(
            "max_grid_kwh"
        )

        if not isinstance(
            maximum,
            (int, float)
        ):
            raise ValueError(
                "grid cap must be numeric"
            )

        if not math.isfinite(
            float(maximum)
        ):
            raise ValueError(
                "grid cap must be finite"
            )

        if maximum < 0:
            raise ValueError(
                "grid cap cannot be negative"
            )

    elif directive_type in {
        "no_charge_window",
        "no_discharge_window",
    }:
        pass

    return directive


def interpret_notes_with_llm(
    notes: list[str],
    battery_capacity: float,
) -> list[dict[str, Any]]:

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured"
        )

    client = genai.Client(
        api_key=api_key
    )

    notes_text = json.dumps(
        notes,
        ensure_ascii=False,
    )

    prompt = f"""
You are the operator-note interpretation component
of an energy scheduling system.

Interpret EVERY operator note independently.

Allowed directive types ONLY:

- solar_reduction
- minimum_battery_reserve
- no_charge_window
- no_discharge_window
- max_grid_window
- no_op

Rules:

1. Return exactly one object for every note.
2. Preserve note_index order: 0, 1, 2, ...
3. Relevant notes must use applies=true.
4. Irrelevant notes must use:
   applies=false
   directive_type="no_op"
   structured_adjustment=null
5. Never invent an energy rule.
6. Never modify demand, solar, tariff, or battery
   parameters.
7. Hours are whole-hour intervals.
8. Hours must be integers from 0 through 23.
9. Hours must be unique and ascending.
10. For solar_reduction, factor means the fraction
    of solar that remains.
11. Example:
    80 percent reduction = factor 0.2.
12. For minimum_battery_reserve, the value is kWh.
13. For max_grid_window, the value is kWh.
14. Do not create any directive type not listed above.
15. Output JSON only.
16. Do not use Markdown code fences.

Required object shape:

{{
  "note_index": 0,
  "applies": true,
  "directive_type": "no_charge_window",
  "structured_adjustment": {{
    "hours": [14, 15]
  }},
  "explanation": "Short explanation."
}}

For no_op:

{{
  "note_index": 0,
  "applies": false,
  "directive_type": "no_op",
  "structured_adjustment": null,
  "explanation": "This note does not affect the schedule."
}}

Battery capacity:

{battery_capacity} kWh

Operator notes:

{notes_text}
"""

    # ---------------------------------------------------------
    # Gemini request with automatic retry
    # ---------------------------------------------------------

    max_attempts = 4
    last_error = None

    for attempt in range(1, max_attempts + 1):

        try:

            print(
                f"Gemini request attempt "
                f"{attempt}/{max_attempts}"
            )

            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )

            break

        except Exception as exc:

            last_error = exc

            error_text = str(exc)

            # Retry temporary server/rate-limit errors.
            temporary_error = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or "429" in error_text
                or "RESOURCE_EXHAUSTED" in error_text
                or "500" in error_text
                or "INTERNAL" in error_text
            )

            if (
                not temporary_error
                or attempt == max_attempts
            ):
                raise RuntimeError(
                    f"Gemini request failed: {exc}"
                ) from exc

            wait_seconds = 2 ** attempt

            print(
                f"Gemini temporarily unavailable. "
                f"Retrying in {wait_seconds} seconds..."
            )

            time.sleep(
                wait_seconds
            )

    else:

        raise RuntimeError(
            f"Gemini request failed: {last_error}"
        )

    # ---------------------------------------------------------
    # Validate response
    # ---------------------------------------------------------

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response"
        )

    text = response.text.strip()

    # Remove accidental Markdown fences.
    if text.startswith("```"):

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        text = "\n".join(
            lines
        ).strip()

    # Parse JSON.
    try:

        parsed = json.loads(text)

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Gemini returned invalid JSON"
        ) from exc

    if not isinstance(parsed, list):

        raise ValueError(
            "Gemini response must be a JSON array"
        )

    if len(parsed) != len(notes):

        raise ValueError(
            "Gemini must return exactly one "
            "directive per note"
        )

    # Deterministic validation.
    validated = []

    for index, directive in enumerate(parsed):

        validated.append(
            validate_directive(
                directive,
                index,
                battery_capacity,
            )
        )

    return validated
