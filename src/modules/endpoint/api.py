from fastapi import FastAPI, HTTPException
from D4.d4_module import (
    fetch_patient_for_assessment,
    get_or_create_assessment
)

app = FastAPI(title="Polypharmacy Risk API")

# run from modules/  uvicorn endpoint.api:app --reload


@app.get("/assessment/{patient_id}")
def get_assessment(patient_id: int):
    # Step 1: fetch patient
    patient = fetch_patient_for_assessment(patient_id)

    if not patient:
        raise HTTPException(
            status_code=404,
            detail=f"Patient {patient_id} not found"
        )

    # Step 2: compute or fetch assessment
    try:
        assessment, medicines = get_or_create_assessment(patient)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    # Step 3: return structured response
    return {
        "patient": {
            "patient_id": patient.get("patient_id"),
            "name": patient.get("name"),
            "age": patient.get("age"),
        },
        "assessment": assessment,
        "medicines": medicines
    }