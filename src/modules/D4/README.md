# Module D4: Polypharmacy Risk Detection

## Overview

The **Polypharmacy Risk Detection** module is designed to evaluate patient medication regimens to identify potential risks associated with polypharmacy. This module acts as an intelligent prescription safety system that flags potential contraindications, age-appropriate warnings, and duplicate therapies, ensuring better patient outcomes.

This module is part of the **D - Drug & Prescription Safety** category.

## Features

- **Risk Assessment Scoring:** Assigns a risk score (0-100) to patient medication regimens.
- **Duplicate Therapy Detection:** Identifies overlaps in therapeutic classes and drugs in active prescriptions.
- **Age-Based Warnings:** Flags medications that may be inappropriate for pediatric or geriatric patients based on their current age.
- **Contraindications:** Checks patient disease history and symptoms against medication-specific contraindications.
- **Recommendations:** Suggests modifications for safer medication routines.

## Tech Stack

### Backend
- **Framework:** FastAPI
- **Database:** Supabase (PostgreSQL)
- **Dependencies:** `fastapi`, `uvicorn`, `supabase`, `python-dotenv`, `requests`

### Frontend
- **Framework:** Streamlit
- **Features:** Interactive dashboard with ER Diagram visualization, Database schema viewer, automated Database triggers review, and Polypharmacy output analysis.

## Database Schema

The module relies on the following core entities:
1. **Patient:** Stores patient details, symptoms, and active medication list.
2. **Medicine:** Stores drug details, age restrictions, and illness contraindications.
3. **Polypharmacy_Assessment:** Stores the computed risk score, alerts, updated medications, and doctor recommendations for a specific patient.

> **Note:** A database trigger (`after_patient_meds_update`) automatically invalidates/re-assesses polypharmacy risks whenever a patient's medication list is modified.

## Installation & Setup

1. **Install Dependencies:**
   Navigate to the `app` directory and install the necessary Python packages.
   ```bash
   cd src/modules/D4/app
   pip install -r requirements.txt
   ```

2. **Environment Variables:**
   Ensure you have a `.env` file in the `app` directory with the necessary Supabase credentials:
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   ```

3. **Run the API Server:**
   Start the FastAPI server from the `D4` directory. It uses Uvicorn under the hood.
   ```bash
   cd src/modules/D4
   python -m app.api
   ```
   The API will be accessible at `http://localhost:8000`.

4. **Run the Frontend (Streamlit):**
   The Streamlit component (`frontend.py`) is designed to be run as an integrated module, but can be viewed loosely via:
   ```bash
   streamlit run app.py
   ```

## Directory Structure

```text
src/modules/D4/
├── app/
│   ├── db/                 # Database configurations and connection clients (Supabase)
│   ├── services/           # Core business logic for patient evaluation and assessment
│   ├── api.py              # FastAPI endpoints
│   ├── requirements.txt    # Backend dependencies
│   └── .env                # Environment variables (not tracked)
├── frontend.py             # Streamlit application interface
└── README.md               # Module documentation
```

## API Endpoints

- `GET /` - Health Check
- `GET /medicines` - Fetch all medicines
- `GET /patients` - Fetch all patients
- `GET /patient/{patient_id}` - Fetch details of a specific patient
- `GET /assessments` - List all computed polypharmacy assessments
- `GET /assessments/patient/{patient_id}` - Get the assessment history for a patient
- `GET /assessment/{patient_id}` - Get or create the latest assessment for a patient
- `POST /assessment/{patient_id}` - Explicitly force-generate a new assessment for a patient