# GridWise

GridWise is an energy optimization API...

## Features

- Gemini-based operator-note interpretation
- Structured directive validation
- OR-Tools energy optimization

## Run Locally

Create a `.env` file:

GEMINI_API_KEY=your_api_key_here

Install dependencies:

pip install -r requirements.txt

Start the server:

uvicorn app.main:app --reload

## Security

Do not commit `.env`, API keys, or `.venv` to GitHub.
