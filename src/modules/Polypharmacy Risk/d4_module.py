import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PATIENT_ID = 1  # change this if you want to assess a different patient by default


@st.cache_resource
def get_supabase() -> Client:
    """Create and cache a Supabase client.

    Expects credentials in either `st.secrets` or environment variables.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        st.error(
            "Supabase credentials not configured. "
            "Set `SUPABASE_URL` and `SUPABASE_KEY` in Streamlit secrets or environment."
        )
        st.stop()

    return create_client(url, key)


def fetch_patient_for_assessment(patient_id: int = DEFAULT_PATIENT_ID):
    """Fetch the patient whose regimen we will assess (default: patient_id = 1)."""
    supabase = get_supabase()
    try:
        resp = (
            supabase.table("Patient")
            .select("*")
            .eq("patient_id", patient_id)
            .limit(1)
            .execute()
        )
        data = resp.data or []
        return data[0] if data else None
    except Exception as e:
        st.error(f"Error fetching patient {patient_id} from Supabase: {e}")
        return None


def fetch_medicines_for_patient(patient_row: dict):
    """Fetch Medicine rows for the comma‑separated medication IDs in the patient record."""
    meds_raw = (patient_row or {}).get("medications") or ""
    med_ids = [m.strip() for m in meds_raw.split(",") if m.strip()]
    if not med_ids:
        return [], []

    # Convert to ints where possible, keep original string IDs as fallback
    numeric_ids = []
    for mid in med_ids:
        try:
            numeric_ids.append(int(mid))
        except ValueError:
            numeric_ids.append(mid)

    supabase = get_supabase()
    try:
        # Supabase-py `in_` works for both ints and strings
        resp = supabase.table("Medicine").select("*").in_("medication_id", numeric_ids).execute()
        return med_ids, (resp.data or [])
    except Exception as e:
        st.error(f"Error fetching medicines from Supabase: {e}")
        return med_ids, []


def compute_polypharmacy_assessment(patient: dict):
    """Compute a polypharmacy assessment for a single patient."""
    patient_id = patient.get("patient_id")
    age = patient.get("age")

    med_id_list, medicines = fetch_medicines_for_patient(patient)
    total_active_meds = len(med_id_list)

    # ---- Duplicate therapy detection (by therapeutic_class) ----
    from collections import defaultdict

    class_groups = defaultdict(list)  # class -> list of med dicts
    for med in medicines:
        t_class = med.get("therapeutic_class")
        if t_class:
            class_groups[t_class].append(med)

    duplicate_therapies = []
    duplicate_remove_ids = set()  # medication_ids (as str) to drop because of duplication
    duplicate_keep_ids = set()    # medication_ids (as str) to keep in each duplicate group

    for cls, meds_in_class in class_groups.items():
        if len(meds_in_class) > 1:
            # Sort by medication_id so the "first" is deterministic
            meds_sorted = sorted(
                meds_in_class,
                key=lambda m: m.get("medication_id") if m.get("medication_id") is not None else 0,
            )
            keep_med = meds_sorted[0]
            keep_id_str = str(keep_med.get("medication_id"))
            duplicate_keep_ids.add(keep_id_str)

            all_names = [m.get("name") or f"ID {m.get('medication_id')}" for m in meds_sorted]
            remove_names = [m.get("name") or f"ID {m.get('medication_id')}" for m in meds_sorted[1:]]

            # Mark all but the first medicine for removal
            for m in meds_sorted[1:]:
                if m.get("medication_id") is not None:
                    duplicate_remove_ids.add(str(m.get("medication_id")))

            duplicate_therapies.append(
                f"These medicines ({', '.join(all_names)}) are duplicate in class '{cls}', "
                f"take only this medicine: {all_names[0]}."
            )

    # ---- Age-based warnings (Beers / STOPP-like) ----
    age_warnings = []
    age_remove_ids = set()  # medication_ids (as str) to drop because of age issues

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
                # age_warning_above/below now holds descriptive risk text
                effects = med.get("age_warning_above/below") or med.get("age_warning_above_below") or ""
                if effects:
                    reason_text = f"and can have the following effects: {effects}"
                else:
                    reason_text = "and may have increased risk in older patients."

            elif min_age is not None and age < min_age:
                out_of_range = True
                reason_text = "and may not be safe for patients below the minimum recommended age."

            if out_of_range:
                age_warnings.append(
                    f"Medicine {name} is outside age-appropriate range "
                    f"[{min_age if min_age is not None else '-'}–"
                    f"{max_age if max_age is not None else '-'}] for age {age} "
                    f"{reason_text} Remove this medicine."
                )
                if med_id_str is not None:
                    age_remove_ids.add(med_id_str)

    # ---- Compute updated regimen after removing duplicates and harmful meds ----
    ids_to_remove = duplicate_remove_ids.union(age_remove_ids)
    updated_med_ids = [mid for mid in med_id_list if str(mid) not in ids_to_remove]

    # ---- Risk score (0–100) ----
    risk_score = 0

    # 1) Base on number of meds (polypharmacy burden) – lower weight
    #    Max 40 points, ~4 points per remaining medication.
    meds_component = min(40, len(updated_med_ids) * 4)
    risk_score += meds_component

    # 2) Age factor – unchanged (up to 20 points)
    if age is not None:
        if age >= 75:
            risk_score += 20
        elif age >= 65:
            risk_score += 10

    # 3) Duplicate therapies – scale with number of duplicate medicines (not just a flat +10)
    #    Each medicine removed for duplication adds 8 points, capped at 24.
    dup_meds_count = len(duplicate_remove_ids)
    dup_component = min(24, dup_meds_count * 8)
    risk_score += dup_component

    # 4) Age-based warnings – scale with number of age-problematic medicines
    #    Each age-inappropriate medicine adds 10 points, capped at 30.
    age_meds_count = len(age_remove_ids)
    age_component = min(30, age_meds_count * 10)
    risk_score += age_component

    # Final cap
    risk_score = float(min(100, risk_score))

    # ---- Recommendations text ----
    recs = []
    
    # Names for clear rendering in the recommendation
    duplicate_names = []
    for cls, meds_in_class in class_groups.items():
        if len(meds_in_class) > 1:
            meds_sorted = sorted(meds_in_class, key=lambda m: m.get("medication_id") if m.get("medication_id") is not None else 0)
            remove_names = [m.get("name") or f"ID {m.get('medication_id')}" for m in meds_sorted[1:]]
            duplicate_names.extend(remove_names)
            
    if duplicate_names:
        recs.append(f"These medicines are duplicates: {', '.join(duplicate_names)} and ")

    age_harmful_names = []
    if age is not None:
        for med in medicines:
            med_id_str = str(med.get("medication_id")) if med.get("medication_id") is not None else None
            if med_id_str in age_remove_ids:
                age_harmful_names.append(med.get("name") or f"ID {med.get('medication_id')}")
                
    if age_harmful_names:
        recs.append(f"these medicines are potentially harmful for the patient's age: {', '.join(age_harmful_names)}. Therefore, remove these from the prescription.")

    if len(updated_med_ids) >= 5:
        recs.append(
            "High pill burden (> 5 meds) remains even after proposing removal of duplicates/high-risk medicines. "
            "Consider further deprescribing where clinically appropriate."
        )
        
    if not recs:
        recs.append("Current regimen appears acceptable. Continue routine monitoring.")

    assessment_row = {
        "patient_id": patient_id,
        "total_active_meds": len(updated_med_ids),
        "risk_score": risk_score,
        "updated_meds": ", ".join(updated_med_ids) if updated_med_ids else "",
        "duplicate_therapies": "; ".join(duplicate_therapies) if duplicate_therapies else "",
        "age_warnings": "; ".join(age_warnings) if age_warnings else "",
        "recommendations": " ".join(recs),
    }

    return assessment_row, medicines


def get_or_create_assessment(patient: dict):
    """Fetch existing assessment if present; otherwise compute and insert a new one."""
    supabase = get_supabase()
    patient_id = patient.get("patient_id")

    try:
        existing = (
            supabase.table("Polypharmacy_Assessment")
            .select("*")
            .eq("patient_id", patient_id)
            .execute()
        )
        if existing.data:
            # We don't have medicines info here; refetch for display
            _, meds = fetch_medicines_for_patient(patient)
            return existing.data[0], meds
    except Exception as e:
        st.warning(f"Error checking existing assessment, will recompute: {e}")

    # Compute new and insert
    assessment_row, medicines = compute_polypharmacy_assessment(patient)

    try:
        inserted = (
            supabase.table("Polypharmacy_Assessment")
            .insert(assessment_row)
            .execute()
        )
        if inserted.data:
            return inserted.data[0], medicines
    except Exception as e:
        st.error(f"Error inserting new assessment: {e}")

    # Fallback if insert failed
    return assessment_row, medicines


def d4_module_detail():
    cat_key = st.session_state.selected_category
    module_code, name, desc, tables, records = st.session_state.selected_module
    
    # Breadcrumb
    st.markdown(f"Category {cat_key.split('-')[0].strip()} > {name}")
    st.markdown(f"# {name}")
    st.markdown(f"*{desc}*")
    
    # Tabs
    tab = st.radio("", ["🏠 Home", "🔗 ER Diagram", "📋 Tables", "🔍 SQL Query", "⚡ Triggers", "📊 Output"], horizontal=True)
    st.divider()
    
    if tab == "🏠 Home":
        st.info(f"**{name}** - {desc}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📥 Input Entities")
            st.success("1️⃣ Patient (Medications, Symptoms)")
            st.success("2️⃣ Medicine (Age Warnings, Contraindications)")
        
        with col2:
            st.markdown("### 📤 Output Entities")
            st.success("1️⃣ Polypharmacy Assessment")
            st.success("2️⃣ Risk Score & Alerts")
            
        st.markdown("### 📊 Module Statistics")
        c1, c2, c3 = st.columns(3)
        
        # Fetch real statistics from Supabase
        supabase = get_supabase()
        
        try:
            # Note: For large tables in production, count exact query might be slow, but it's fine for small to medium sets
            patients_resp = supabase.table("Patient").select("patient_id", count="exact").limit(1).execute()
            patient_count = patients_resp.count if patients_resp.count is not None else 0
        except Exception:
            patient_count = "N/A"
            
        try:
            meds_resp = supabase.table("Medicine").select("medication_id", count="exact").limit(1).execute()
            med_count = meds_resp.count if meds_resp.count is not None else 0
        except Exception:
            med_count = "N/A"
            
        try:
            assess_resp = supabase.table("Polypharmacy_Assessment").select("assessment_id", count="exact").limit(1).execute()
            assessment_count = assess_resp.count if assess_resp.count is not None else 0
        except Exception:
            assessment_count = "N/A"

        c1.metric("Patients", str(patient_count))
        c2.metric("Medicines", str(med_count))
        c3.metric("Assessments", str(assessment_count))
    
    elif tab == "🔗 ER Diagram":
        st.markdown("### Entity Relationship Diagram")
        st.image("assets/image.png", caption="Polypharmacy Risk Detection Schema", width=800)

    elif tab == "📋 Tables":
        st.markdown("### Database Schema")
        
        with st.expander("1️⃣ **Patient** Table", expanded=True):
            st.table({
                "Column Name": ["patient_id", "name", "age", "gender", "doctor_id", "symptoms", "medications"],
                "Data Type": ["INT (PK)", "VARCHAR", "INT", "VARCHAR", "INT", "TEXT", "TEXT"],
                "Description": ["Unique ID", "Full Name", "Age in years", "M/F", "Assigned Doctor", "Comma-sep symptoms", "Comma-sep medication IDs"]
            })

        with st.expander("2️⃣ **Medicine** Table"):
            st.table({
                "Column Name": ["medication_id", "name", "salt", "atc_code", "therapeutic_class", "min_age", "max_age", "age_warning_above_below", "contraindicated_diseases"],
                "Data Type": ["INT (PK)", "VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR", "INT", "INT", "BOOLEAN", "TEXT"],
                "Description": ["Unique ID", "Drug Name", "Chemical Salt", "Anatomical Code", "Class", "Min Age", "Max Age", "Age Warnings", "Disease Constraint"]
            })
            
        with st.expander("3️⃣ **Polypharmacy_Assessment** Table"):
            st.table({
                "Column Name": ["assessment_id", "patient_id", "total_active_meds", "risk_score", "updated_meds", "duplicate_therapies", "age_warnings", "recommendations"],
                "Data Type": ["INT (PK)", "INT (FK)", "INT", "DECIMAL", "TEXT", "TEXT", "TEXT", "TEXT"],
                "Description": ["Unique ID", "Links to Patient", "Count of active meds", "0-100 Score", "Review status", "Duplicate alerts", "Age-based alerts", "Doctor action items"]
            })
            
    elif tab == "🔍 SQL Query":
        st.markdown("### Sample SQL Queries")
        
        st.subheader("1. Identify High-Risk Patients")
        st.code("""
SELECT p.name, p.age, pa.risk_score, pa.recommendations
FROM "Patient" p
JOIN "Polypharmacy_Assessment" pa ON p.patient_id = pa.patient_id
WHERE pa.risk_score >= 75
ORDER BY pa.risk_score DESC;
        """, language="sql")
        
        st.subheader("2. Patients with Duplicate Therapies Detected")
        st.code("""
SELECT p.name, pa.risk_score, pa.duplicate_therapies 
FROM "Patient" p
JOIN "Polypharmacy_Assessment" pa ON p.patient_id = pa.patient_id
WHERE pa.duplicate_therapies IS NOT NULL AND pa.duplicate_therapies != '';
        """, language="sql")
        
        if st.button("▶️ Execute Queries", type="primary"):
            supabase = get_supabase()
            
            st.markdown("#### **Query 1 Results: High-Risk Patients**")
            try:
                # Fetch assessments
                resp1 = supabase.table("Polypharmacy_Assessment").select("patient_id, risk_score, recommendations").gte("risk_score", 75).order("risk_score", desc=True).execute()
                
                if resp1.data:
                    # Fetch linked patients
                    p_ids = [r["patient_id"] for r in resp1.data]
                    if p_ids:
                        patients_resp = supabase.table("Patient").select("patient_id, name, age").in_("patient_id", p_ids).execute()
                        patient_dict = {p["patient_id"]: p for p in (patients_resp.data or [])}
                    else:
                        patient_dict = {}
                    
                    formatted_data1 = []
                    for row in resp1.data:
                        p_info = patient_dict.get(row["patient_id"], {})
                        formatted_data1.append({
                            "Patient Name": p_info.get("name", "Unknown"),
                            "Age": p_info.get("age", "N/A"),
                            "Risk Score": row.get("risk_score"),
                            "Recommendations": row.get("recommendations")
                        })
                    st.dataframe(formatted_data1, use_container_width=True)
                    st.success(f"Query 1 executed successfully! {len(formatted_data1)} rows returned.")
                else:
                    st.info("No high-risk patients found.")
            except Exception as e:
                st.error(f"Error executing Query 1: {e}")

            st.markdown("#### **Query 2 Results: Patients with Duplicate Therapies**")
            try:
                # Fetch assessments
                resp2 = supabase.table("Polypharmacy_Assessment").select("patient_id, risk_score, duplicate_therapies").neq("duplicate_therapies", "").execute()
                
                if resp2.data:
                    # Filter out null strings or purely whitespace
                    valid_resp2 = [r for r in resp2.data if r.get("duplicate_therapies") and r.get("duplicate_therapies").strip()]
                    
                    if valid_resp2:
                        p_ids = [r["patient_id"] for r in valid_resp2]
                        if p_ids:
                            patients_resp = supabase.table("Patient").select("patient_id, name").in_("patient_id", p_ids).execute()
                            patient_dict = {p["patient_id"]: p for p in (patients_resp.data or [])}
                        else:
                            patient_dict = {}
                        
                        formatted_data2 = []
                        for row in valid_resp2:
                            p_info = patient_dict.get(row["patient_id"], {})
                            formatted_data2.append({
                                "Patient Name": p_info.get("name", "Unknown"),
                                "Risk Score": row.get("risk_score"),
                                "Duplicate Therapies": row.get("duplicate_therapies")
                            })
                        st.dataframe(formatted_data2, use_container_width=True)
                        st.success(f"Query 2 executed successfully! {len(formatted_data2)} rows returned.")
                    else:
                        st.info("No patients with duplicate therapies found.")
                else:
                    st.info("No patients with duplicate therapies found.")
            except Exception as e:
                st.error(f"Error executing Query 2: {e}")

    elif tab == "⚡ Triggers":
        st.markdown("### Database Triggers")
        
        st.subheader("Trigger: Auto-Reassess Polypharmacy Risk")
        st.code("""
CREATE OR REPLACE FUNCTION trigger_reassess_polypharmacy()
RETURNS TRIGGER AS $$
BEGIN
    -- If the patient's medication list changes, we invalidate the current assessment
    IF OLD.medications IS DISTINCT FROM NEW.medications THEN
        -- Delete the outdated assessment to force a re-evaluation on the application side.
        -- When the dashboard is opened, get_or_create_assessment() will run dynamically.
        DELETE FROM "Polypharmacy_Assessment" WHERE patient_id = NEW.patient_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER after_patient_meds_update
AFTER UPDATE ON "Patient"
FOR EACH ROW
EXECUTE FUNCTION trigger_reassess_polypharmacy();
        """, language="sql")
        
        st.info(
            "**How it works:** This PostgreSQL trigger ensures that whenever a doctor updates a patient's medications in the `Patient` table, "
            "the existing `Polypharmacy_Assessment` record is deleted. The next time the dashboard is loaded for that patient, a fresh risk assessment "
            "will be dynamically computed and inserted into the database. This guarantees the risk score is always perfectly synced with the patient's current regimen."
        )

    elif tab == "📊 Output":
        st.markdown("### Module Output")

        # Fetch the default patient and compute/fetch their assessment
        patient = fetch_patient_for_assessment()
        if not patient:
            st.error(
                f"No patient found with patient_id = {DEFAULT_PATIENT_ID} in `Patient` table. "
                "Insert this row first to see the assessment."
            )
            return

        assessment, medicines = get_or_create_assessment(patient)

        # Patient Header
        st.success("✅ **Risk Assessment Completed**")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"📋 **Patient ID:** {patient.get('patient_id')}")
        with col2:
            st.info(f"👤 **Name:** {patient.get('name', 'Unknown')}")
        with col3:
            st.info(f"📅 **Age:** {patient.get('age', 'N/A')} Years")

        st.divider()

        # Risk Score Section
        st.markdown("#### ⚠️ Risk Analysis")
        risk_col1, risk_col2, risk_col3 = st.columns(3)

        risk = assessment.get("risk_score", 0)
        level = "High Risk" if risk >= 75 else ("Moderate" if risk >= 40 else "Low")
        delta_color = "inverse" if risk >= 75 else "normal"

        with risk_col1:
            st.metric(label="Risk Score", value=f"{risk:.0f} / 100", delta=level, delta_color=delta_color)
        with risk_col2:
            st.metric(
                label="Active Medications",
                value=str(assessment.get("total_active_meds", 0)),
            )
        with risk_col3:
            dup_list = (assessment.get("duplicate_therapies") or "").split(";") if assessment.get("duplicate_therapies") else []
            st.metric(
                label="Duplicate / Overlap Flags",
                value=str(len([d for d in dup_list if d.strip()])),
            )

        st.divider()

        # Detailed Findings
        c1, c2 = st.columns(2)

        with c1:
            st.warning("#### 🚫 Duplicate / Overlapping Therapies")
            if dup_list:
                for d in dup_list:
                    if d.strip():
                        st.write(f"- {d.strip()}")
            else:
                st.write("No duplicate or overlapping therapies detected.")

        with c2:
            st.error("#### 👴 Age-Based Warnings")
            age_warnings = (assessment.get("age_warnings") or "").split(";") if assessment.get("age_warnings") else []
            if age_warnings:
                for w in age_warnings:
                    if w.strip():
                        st.write(f"- {w.strip()}")
            else:
                st.write("No age-based medication warnings for this patient.")

        st.divider()

        # Recommendations
        st.markdown("#### 🧭 Recommendations")
        st.info(assessment.get("recommendations") or "No specific recommendations generated.")

        # Updated regimen table
        if medicines:
            st.markdown("#### 💊 Updated Medication Regimen")
            
            # Filter medicines based on the updated_meds list in the assessment
            updated_meds_str = assessment.get("updated_meds", "")
            # Handle potential None or empty values gracefully
            updated_med_ids_str_list = [mid.strip() for mid in (updated_meds_str or "").split(",") if mid.strip()]
            
            updated_medicines = []
            for med in medicines:
                med_id_str = str(med.get("medication_id")) if med.get("medication_id") is not None else None
                # If med_id is in the updated list, OR if updated list is empty (which might mean either no meds or all meds removed, but typically if it's empty we show nothing, but we'll fall back to showing it if we can't parse it well. Let's just strictly check)
                if med_id_str in updated_med_ids_str_list:
                    updated_medicines.append(med)
            
            if updated_medicines:
                st.table(
                    [
                        {
                            "Medication": med.get("name"),
                            "Salt": med.get("salt"),
                            "ATC Code": med.get("atc_code"),
                            "Therapeutic Class": med.get("therapeutic_class"),
                            "Min Age": med.get("min_age") if med.get("min_age") is not None else "NULL",
                            "Max Age": med.get("max_age") if med.get("max_age") is not None else "NULL",
                        }
                        for med in updated_medicines
                    ]
                )
            else:
                st.info("No medications remain in the updated regimen.")

        st.divider()