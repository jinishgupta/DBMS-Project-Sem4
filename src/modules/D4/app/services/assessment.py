from collections import defaultdict
from app.services.medicine import fetch_medicines_for_patient
from app.db.supabase_client import get_supabase


def compute_polypharmacy_assessment(patient: dict):
    patient_id = patient.get("patient_id")
    age = patient.get("age")
    patient_symptoms = patient.get("symptoms", "")
    
    med_id_list, medicines = fetch_medicines_for_patient(patient)
    
    class_groups = defaultdict(list)
    for med in medicines:
        t_class = med.get("therapeutic_class")
        if t_class:
            class_groups[t_class].append(med)
    
    duplicate_therapies = []
    duplicate_remove_ids = set()
    duplicate_keep_ids = set()
    
    for cls, meds_in_class in class_groups.items():
        if len(meds_in_class) > 1:
            meds_sorted = sorted(meds_in_class, key=lambda m: m.get("medication_id") if m.get("medication_id") is not None else 0)
            keep_med = meds_sorted[0]
            keep_id_str = str(keep_med.get("medication_id"))
            duplicate_keep_ids.add(keep_id_str)
            
            all_names = [m.get("name") or f"ID {m.get('medication_id')}" for m in meds_sorted]
            
            for m in meds_sorted[1:]:
                if m.get("medication_id") is not None:
                    duplicate_remove_ids.add(str(m.get("medication_id")))
            
            duplicate_therapies.append(f"These medicines ({', '.join(all_names)}) are duplicate in class '{cls}', take only this medicine: {all_names[0]}.")
    
    age_warnings = []
    age_remove_ids = set()
    
    if age is not None:
        for med in medicines:
            name = med.get("name") or f"ID {med.get('medication_id')}"
            min_age = med.get("min_age")
            max_age = med.get("max_age")
            med_id_str = str(med.get("medication_id")) if med.get("medication_id") is not None else None
            
            out_of_range = False
            reason_text = ""
            
            if max_age is not None and age > max_age:
                out_of_range = True
                effects = med.get("age_warning_above/below") or med.get("age_warning_above_below") or ""
                reason_text = f"and can have the following effects: {effects}" if effects else "and may have increased risk in older patients."
            elif min_age is not None and age < min_age:
                out_of_range = True
                reason_text = "and may not be safe for patients below the minimum recommended age."
            
            if out_of_range:
                age_warnings.append(f"Medicine {name} is outside age-appropriate range [{min_age if min_age is not None else '-'}–{max_age if max_age is not None else '-'}] for age {age} {reason_text} Remove this medicine.")
                if med_id_str is not None:
                    age_remove_ids.add(med_id_str)
    
    contraindication_warnings = []
    contraindication_remove_ids = set()
    
    patient_conditions = set()
    if patient_symptoms:
        raw_conditions = patient_symptoms.replace(";", ",").split(",")
        patient_conditions = {s.strip().lower() for s in raw_conditions if s.strip()}
    
    for med in medicines:
        name = med.get("name") or f"ID {med.get('medication_id')}"
        contraindicated = med.get("contraindicated_diseases") or med.get("contraindicated_disease") or ""
        med_id_str = str(med.get("medication_id")) if med.get("medication_id") is not None else None
        
        if contraindicated and patient_conditions:
            contraindicated_raw = contraindicated.replace(";", ",").split(",")
            contraindicated_list = []
            
            for item in contraindicated_raw:
                item = item.strip().lower()
                if not item:
                    continue
                
                item = item.split("(")[0].strip()
                
                if " or " in item:
                    parts = item.split(" or ")
                    for part in parts:
                        part = part.strip()
                        if part:
                            contraindicated_list.append(part)
                else:
                    contraindicated_list.append(item)
            
            matched_conditions = []
            for patient_cond in patient_conditions:
                for contra_cond in contraindicated_list:
                    if patient_cond == contra_cond:
                        matched_conditions.append(patient_cond)
                        break
                    elif patient_cond in contra_cond or contra_cond in patient_cond:
                        matched_conditions.append(f"{patient_cond} (matches: {contra_cond})")
                        break
            
            if matched_conditions:
                matched_str = ", ".join(matched_conditions)
                contraindication_warnings.append(f"Medicine {name} is contraindicated for patient's condition(s): {matched_str}. This medication should NOT be prescribed. Remove immediately.")
                if med_id_str is not None:
                    contraindication_remove_ids.add(med_id_str)
    
    ids_to_remove = duplicate_remove_ids.union(age_remove_ids).union(contraindication_remove_ids)
    updated_med_ids = [mid for mid in med_id_list if str(mid) not in ids_to_remove]
    
    risk_score = 0
    risk_score += min(40, len(updated_med_ids) * 4)
    
    if age is not None:
        if age >= 75:
            risk_score += 20
        elif age >= 65:
            risk_score += 10
    
    risk_score += min(24, len(duplicate_remove_ids) * 8)
    risk_score += min(30, len(age_remove_ids) * 10)
    risk_score += min(30, len(contraindication_remove_ids) * 15)
    risk_score = float(min(100, risk_score))
    
    recs = []
    
    contraindication_names = [med.get("name") or f"ID {med.get('medication_id')}" for med in medicines if str(med.get("medication_id")) in contraindication_remove_ids]
    if contraindication_names:
        recs.append(f"⚠️ CRITICAL: These medicines are contraindicated for patient's conditions: {', '.join(contraindication_names)}. IMMEDIATE REMOVAL REQUIRED to prevent serious adverse events.")
    
    duplicate_names = []
    for cls, meds_in_class in class_groups.items():
        if len(meds_in_class) > 1:
            meds_sorted = sorted(meds_in_class, key=lambda m: m.get("medication_id") if m.get("medication_id") is not None else 0)
            remove_names = [m.get("name") or f"ID {m.get('medication_id')}" for m in meds_sorted[1:]]
            duplicate_names.extend(remove_names)
    
    if duplicate_names:
        recs.append(f"These medicines are therapeutic duplicates: {', '.join(duplicate_names)}. Remove to avoid unnecessary toxicity and drug burden.")
    
    age_harmful_names = [med.get("name") or f"ID {med.get('medication_id')}" for med in medicines if str(med.get("medication_id")) in age_remove_ids]
    if age_harmful_names:
        recs.append(f"These medicines are age-inappropriate (Beers Criteria): {', '.join(age_harmful_names)}. Consider safer alternatives to reduce fall risk, cognitive impairment, and adverse events.")
    
    if len(updated_med_ids) >= 5:
        recs.append(f"High medication burden ({len(updated_med_ids)} medications) remains. Consider deprescribing non-essential medications to reduce pill burden and interaction risk.")
    
    if not recs:
        recs.append("Current medication regimen appears clinically appropriate. Continue routine monitoring for adverse effects.")
    
    assessment_row = {
        "patient_id": patient_id,
        "total_active_meds": len(updated_med_ids),
        "risk_score": risk_score,
        "updated_meds": ", ".join(updated_med_ids) if updated_med_ids else "",
        "duplicate_therapies": "; ".join(duplicate_therapies) if duplicate_therapies else "",
        "age_warnings": "; ".join(age_warnings) if age_warnings else "",
        "contraindication_warnings": "; ".join(contraindication_warnings) if contraindication_warnings else "",
        "recommendations": " ".join(recs),
    }
    
    return assessment_row, medicines


def create_new_assessment(patient: dict):
    supabase = get_supabase()
    assessment_row, medicines = compute_polypharmacy_assessment(patient)
    
    try:
        from datetime import datetime
        assessment_row["created_at"] = datetime.utcnow().isoformat()
    except Exception:
        pass
    
    try:
        inserted = supabase.table("Polypharmacy_Assessment").insert(assessment_row).execute()
        if inserted.data:
            return inserted.data[0], medicines
    except Exception as e:
        print(f"Error inserting assessment: {e}")
    
    return assessment_row, medicines


def get_or_create_assessment(patient: dict):
    supabase = get_supabase()
    patient_id = patient.get("patient_id")
    
    try:
        try:
            existing = supabase.table("Polypharmacy_Assessment").select("*").eq("patient_id", patient_id).order("created_at", desc=True).limit(1).execute()
        except Exception:
            existing = supabase.table("Polypharmacy_Assessment").select("*").eq("patient_id", patient_id).limit(1).execute()
        
        if existing.data:
            _, meds = fetch_medicines_for_patient(patient)
            return existing.data[0], meds
    except Exception as e:
        print(f"Error fetching existing assessment: {e}")
    
    return create_new_assessment(patient)


def get_all_assessments_for_patient(patient_id: int):
    supabase = get_supabase()
    try:
        resp = supabase.table("Polypharmacy_Assessment").select("*").eq("patient_id", patient_id).order("created_at", desc=True).execute()
    except Exception:
        resp = supabase.table("Polypharmacy_Assessment").select("*").eq("patient_id", patient_id).execute()
    return resp.data or []


def fetch_all_assessments():
    supabase = get_supabase()
    resp = supabase.table("Polypharmacy_Assessment").select("*").execute()
    return resp.data or []
