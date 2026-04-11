from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.services.patient import fetch_patient, fetch_all_patients
from app.services.assessment import get_or_create_assessment, fetch_all_assessments, fetch_assessment_by_id
from app.db.supabase_client import get_supabase
from app.services.medicine import fetch_medicines_for_patient
import time

app = FastAPI(
    title="Polypharmacy Risk Detection API",
    description="API for detecting polypharmacy risks and medication interactions",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Polypharmacy Risk Detection API is running",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.get("/medicines")
def list_medicines():
    try:
        supabase = get_supabase()
        resp = supabase.table("Medicine").select("*").execute()
        medicines = resp.data or []
        return {"medicines": medicines, "count": len(medicines)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching medicines: {str(e)}")


@app.get("/patients")
def list_patients():
    try:
        patients = fetch_all_patients()
        return {"patients": patients, "count": len(patients)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching patients: {str(e)}")


@app.get("/patient/{patient_id}")
def get_patient(patient_id: int):
    try:
        patient = fetch_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching patient: {str(e)}")


@app.get("/assessments")
def list_assessments():
    try:
        assessments = fetch_all_assessments()
        return {"assessments": assessments, "count": len(assessments)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching assessments: {str(e)}")


@app.get("/assessment/{patient_id}")
def get_assessment(patient_id: int):
    start_time = time.time()
    
    try:
        patient = fetch_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        assessment, medicines = get_or_create_assessment(patient)
        
        elapsed = time.time() - start_time
        
        return {
            "patient": patient,
            "assessment": assessment,
            "medicines": medicines
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Error processing assessment: {str(e)}")


@app.get("/assessment/detail/{assessment_id}")
def get_assessment_by_id(assessment_id: int):
    try:
        assessment = fetch_assessment_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
            
        patient = fetch_patient(assessment["patient_id"])
        _, medicines = fetch_medicines_for_patient(patient)
        
        return {
            "patient": patient,
            "assessment": assessment,
            "medicines": medicines
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching exact assessment: {str(e)}")


@app.get("/assessments/patient/{patient_id}")
def get_patient_assessments(patient_id: int):
    try:
        from app.services.assessment import get_all_assessments_for_patient
        
        patient = fetch_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        assessments = get_all_assessments_for_patient(patient_id)
        
        return {
            "patient": patient,
            "assessments": assessments,
            "count": len(assessments)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching assessments: {str(e)}")


@app.post("/assessment/{patient_id}")
def create_assessment(patient_id: int):
    try:
        from app.services.assessment import create_new_assessment
        
        patient = fetch_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        assessment, medicines = create_new_assessment(patient)
        
        return {
            "patient": patient,
            "assessment": assessment,
            "medicines": medicines,
            "message": "New assessment created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating assessment: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
