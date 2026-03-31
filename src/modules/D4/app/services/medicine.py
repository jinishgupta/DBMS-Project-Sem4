from app.db.supabase_client import get_supabase


def fetch_medicines_for_patient(patient_row: dict):
    meds_raw = (patient_row or {}).get("medications") or ""
    med_ids = [m.strip() for m in meds_raw.split(",") if m.strip()]
    
    if not med_ids:
        return [], []
    
    numeric_ids = []
    for mid in med_ids:
        try:
            numeric_ids.append(int(mid))
        except ValueError:
            numeric_ids.append(mid)
    
    supabase = get_supabase()
    resp = supabase.table("Medicine").select("*").in_("medication_id", numeric_ids).execute()
    
    return med_ids, (resp.data or [])
