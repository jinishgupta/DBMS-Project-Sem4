from app.db.supabase_client import get_supabase


def fetch_patient(patient_id: int):
    supabase = get_supabase()
    resp = supabase.table("Patient").select("*").eq("patient_id", patient_id).limit(1).execute()
    data = resp.data or []
    return data[0] if data else None


def fetch_all_patients():
    supabase = get_supabase()
    resp = supabase.table("Patient").select("*").execute()
    return resp.data or []
