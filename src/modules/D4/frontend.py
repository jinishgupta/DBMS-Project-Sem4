import streamlit as st
import requests
from typing import Optional
from collections import defaultdict
from datetime import datetime

API_BASE_URL = "http://localhost:8000"


def call_api(endpoint: str, method: str = "GET", timeout: int = 30) -> Optional[dict]:
    try:
        url = f"{API_BASE_URL}{endpoint}"
        response = requests.request(method, url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to API. Make sure the FastAPI server is running on port 8000.")
        st.info("💡 **Start the API server:** `cd src/modules/D4 && python -m app.api`")
        return None
    except requests.exceptions.Timeout:
        st.error(f"⏱️ API request timed out after {timeout} seconds.")
        st.info("💡 Try refreshing the page or check the API server logs.")
        return None
    except requests.exceptions.HTTPError as e:
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except:
            error_detail = e.response.text
        st.error(f"❌ API Error: {e.response.status_code}")
        st.code(error_detail)
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None


def check_api_health():
    health_data = call_api("/")
    if health_data:
        st.success(f"✅ API Connected - {health_data.get('message', 'Running')}")
        return True
    return False


def render_assessment_card(assessment: dict, patient_name: str, patient_age: int = None, show_date: bool = False):
    risk = assessment.get("risk_score", 0)
    level = "🔴 High Risk" if risk >= 75 else ("🟡 Moderate" if risk >= 40 else "🟢 Low")
    border_color = "#ff4444" if risk >= 75 else ("#ffaa00" if risk >= 40 else "#44ff44")
    
    with st.container():
        st.markdown(f'<div style="border-left: 4px solid {border_color}; padding-left: 15px; margin-bottom: 20px;">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(f"### {patient_name}")
            caption_parts = [f"Patient ID: {assessment.get('patient_id')}"]
            if patient_age:
                caption_parts.append(f"Age: {patient_age}")
            if show_date and assessment.get("created_at"):
                try:
                    created = datetime.fromisoformat(assessment.get("created_at").replace("Z", "+00:00"))
                    caption_parts.append(f"Date: {created.strftime('%Y-%m-%d %H:%M')}")
                except:
                    pass
            st.caption(" | ".join(caption_parts))
        with col2:
            st.metric("Risk Score", f"{risk:.0f}/100")
        with col3:
            st.markdown(f"**{level}**")
        
        if show_date:
            st.caption(f"Assessment ID: {assessment.get('assessment_id', 'N/A')}")
        
        if st.button(f"View Details →", key=f"view_{assessment.get('assessment_id', assessment.get('patient_id'))}", use_container_width=True):
            st.session_state.selected_assessment_id = assessment.get('assessment_id')
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()


def render_assessment_detail(assessment_id: int):
    with st.spinner(f"Loading assessment {assessment_id}..."):
        data = call_api(f"/assessment/id/{assessment_id}", timeout=60)
    
    if not data:
        st.error("Unable to load assessment data.")
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("← Back", use_container_width=True):
                st.session_state.selected_assessment_id = None
                st.rerun()
        with col2:
            st.info("💡 Check that the API server is running and the database is accessible.")
        return
    
    patient = data.get("patient", {})
    assessment = data.get("assessment", {})
    medicines = data.get("medicines", [])
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.selected_assessment_id = None
            st.rerun()
    with col2:
        st.markdown("### Assessment Details")
    
    st.markdown("---")
    st.success("✅ **Risk Assessment Completed**")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"� **Patient ID:** {patient.get('patient_id')}")
    with col2:
        st.info(f"👤 **Name:** {patient.get('name', 'Unknown')}")
    with col3:
        st.info(f"📅 **Age:** {patient.get('age', 'N/A')} Years")
    
    st.divider()
    st.markdown("#### ⚠️ Risk Analysis")
    
    risk = assessment.get("risk_score", 0)
    level = "High Risk" if risk >= 75 else ("Moderate" if risk >= 40 else "Low")
    delta_color = "inverse" if risk >= 75 else "normal"
    
    risk_col1, risk_col2, risk_col3 = st.columns(3)
    with risk_col1:
        st.metric("Risk Score", f"{risk:.0f} / 100", delta=level, delta_color=delta_color)
    with risk_col2:
        st.metric("Active Medications", str(assessment.get("total_active_meds", 0)))
    with risk_col3:
        dup_list = (assessment.get("duplicate_therapies") or "").split(";") if assessment.get("duplicate_therapies") else []
        st.metric("Duplicate / Overlap Flags", str(len([d for d in dup_list if d.strip()])))
    
    st.divider()
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.warning("#### � Duplicate Therapies")
        if dup_list and any(d.strip() for d in dup_list):
            for d in dup_list:
                if d.strip():
                    st.write(f"- {d.strip()}")
        else:
            st.write("✅ No duplicates detected.")
    
    with c2:
        st.error("#### 👴 Age-Based Warnings")
        age_warnings = (assessment.get("age_warnings") or "").split(";") if assessment.get("age_warnings") else []
        if age_warnings and any(w.strip() for w in age_warnings):
            for w in age_warnings:
                if w.strip():
                    st.write(f"- {w.strip()}")
        else:
            st.write("✅ No age warnings.")
    
    with c3:
        st.error("#### ⚠️ Contraindications")
        contraindication_warnings = (assessment.get("contraindication_warnings") or "").split(";") if assessment.get("contraindication_warnings") else []
        if contraindication_warnings and any(w.strip() for w in contraindication_warnings):
            for w in contraindication_warnings:
                if w.strip():
                    st.write(f"- {w.strip()}")
        else:
            st.write("✅ No contraindications.")
    
    st.divider()
    st.markdown("#### 🧭 Recommendations")
    st.info(assessment.get("recommendations") or "No specific recommendations generated.")
    
    if medicines:
        st.markdown("#### 💊 Updated Medication Regimen")
        updated_meds_str = assessment.get("updated_meds", "")
        updated_med_ids_str_list = [mid.strip() for mid in (updated_meds_str or "").split(",") if mid.strip()]
        
        updated_medicines = [med for med in medicines if str(med.get("medication_id")) in updated_med_ids_str_list]
        
        if updated_medicines:
            st.table([{
                "Medication": med.get("name"),
                "Salt": med.get("salt"),
                "ATC Code": med.get("atc_code"),
                "Therapeutic Class": med.get("therapeutic_class"),
                "Min Age": med.get("min_age") if med.get("min_age") is not None else "NULL",
                "Max Age": med.get("max_age") if med.get("max_age") is not None else "NULL",
            } for med in updated_medicines])
        else:
            st.info("No medications remain in the updated regimen.")


def d4_module_detail():
    cat_key = st.session_state.get("selected_category", "D - Drug & Prescription Safety")
    module_code, name, desc, tables, records = st.session_state.selected_module
    
    st.markdown(f"Category {cat_key.split('-')[0].strip()} > {name}")
    st.markdown(f"# {name}")
    st.markdown(f"*{desc}*")
        
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
        
        with st.spinner("Loading statistics..."):
            patients_data = call_api("/patients")
            medicines_data = call_api("/medicines")
            assessments_data = call_api("/assessments")
        
        c1.metric("Patients", str(patients_data.get("count", 0) if patients_data else 0))
        c2.metric("Medicines", str(medicines_data.get("count", 0) if medicines_data else 0))
        c3.metric("Assessments", str(assessments_data.get("count", 0) if assessments_data else 0))
    
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
                "Column Name": ["assessment_id", "patient_id", "total_active_meds", "risk_score", "updated_meds", "duplicate_therapies", "age_warnings", "recommendations","contraindiction_warnings","created_at"],
                "Data Type": ["INT (PK)", "INT (FK)", "INT", "DECIMAL", "TEXT", "TEXT", "TEXT", "TEXT","TEXT","TIMESTAMP"],
                "Description": ["Unique ID", "Links to Patient", "Count of active meds", "0-100 Score", "Review status", "Duplicate alerts", "Age-based alerts", "Doctor action items","Contraindiction alerts","Time of assessment"]
            })
    
    elif tab == "🔍 SQL Query":
        st.markdown("### Sample SQL Queries")
        st.subheader("1. Identify High-Risk Patients")
        st.code("""SELECT p.name, p.age, pa.risk_score, pa.recommendations
FROM "Patient" p
JOIN "Polypharmacy_Assessment" pa ON p.patient_id = pa.patient_id
WHERE pa.risk_score >= 75
ORDER BY pa.risk_score DESC;""", language="sql")
        
        st.subheader("2. Patients with Duplicate Therapies")
        st.code("""SELECT p.name, pa.risk_score, pa.duplicate_therapies 
FROM "Patient" p
JOIN "Polypharmacy_Assessment" pa ON p.patient_id = pa.patient_id
WHERE pa.duplicate_therapies IS NOT NULL AND pa.duplicate_therapies != '';""", language="sql")
        
        st.info("💡 These queries are handled by the API. Use the Output tab to view results.")
    
    elif tab == "⚡ Triggers":
        st.markdown("### Database Triggers")
        st.subheader("Trigger: Auto-Reassess Polypharmacy Risk")
        st.code("""CREATE OR REPLACE FUNCTION trigger_reassess_polypharmacy()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.medications IS DISTINCT FROM NEW.medications THEN
        DELETE FROM "Polypharmacy_Assessment" WHERE patient_id = NEW.patient_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER after_patient_meds_update
AFTER UPDATE ON "Patient"
FOR EACH ROW
EXECUTE FUNCTION trigger_reassess_polypharmacy();""", language="sql")
        
        st.info("**How it works:** When a doctor updates patient medications, the existing assessment is deleted and a fresh risk assessment is computed on the next request.")
    
    elif tab == "📊 Output":
        st.markdown("### Module Output")
        
        if "selected_assessment_id" in st.session_state and st.session_state.selected_assessment_id:
            render_assessment_detail(st.session_state.selected_assessment_id)
        else:
            assessments_data = call_api("/assessments")
            patients_data = call_api("/patients")
            
            if not assessments_data or not patients_data:
                st.warning("⚠️ Unable to load data. Please check API connection.")
                return
            
            assessments = assessments_data.get("assessments", [])
            patients = {p["patient_id"]: p for p in patients_data.get("patients", [])}
            
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown("### 💊 All Polypharmacy Assessments")
            with col2:
                if st.button("🔄 Refresh Data", use_container_width=True):
                    st.rerun()
            with col3:
                if patients and st.button("➕ Create Assessment", use_container_width=True):
                    st.session_state.show_create_modal = True
            
            if st.session_state.get("show_create_modal", False):
                with st.container():
                    st.markdown("#### Create New Assessment")
                    patient_options = {f"{p.get('name', 'Unknown')} (ID: {pid})": pid for pid, p in patients.items()}
                    selected_patient = st.selectbox("Select Patient:", options=list(patient_options.keys()), key="new_assessment_patient")
                    
                    col_create, col_cancel = st.columns(2)
                    with col_create:
                        if st.button("✅ Create", use_container_width=True):
                            patient_id = patient_options[selected_patient]
                            with st.spinner(f"Creating assessment for {selected_patient}..."):
                                result = call_api(f"/assessment/{patient_id}", method="POST", timeout=60)
                            if result:
                                st.success("✅ Assessment created successfully!")
                                st.session_state.show_create_modal = False
                                st.rerun()
                            else:
                                st.error("Failed to create assessment.")
                    with col_cancel:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.session_state.show_create_modal = False
                            st.rerun()
            
            st.divider()
            
            if not assessments:
                st.info("📋 No assessments found. Create assessments using the button above.")
                st.markdown("#### Available Patients")
                if patients:
                    for patient_id, patient in patients.items():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"**{patient.get('name', 'Unknown')}** (ID: {patient_id})")
                        with col2:
                            st.write(f"Age: {patient.get('age', 'N/A')}")
                        with col3:
                            if st.button("Create Assessment", key=f"create_{patient_id}"):
                                st.session_state.selected_assessment_id = patient_id
                                st.rerun()
                return
            
            high_risk = sum(1 for a in assessments if a.get("risk_score", 0) >= 75)
            moderate_risk = sum(1 for a in assessments if 40 <= a.get("risk_score", 0) < 75)
            low_risk = sum(1 for a in assessments if a.get("risk_score", 0) < 40)
            
            stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
            stat_col1.metric("Total Assessments", len(assessments))
            stat_col2.metric("🔴 High Risk", high_risk)
            stat_col3.metric("🟡 Moderate Risk", moderate_risk)
            stat_col4.metric("🟢 Low Risk", low_risk)
            
            st.divider()
            
            assessments_by_patient = defaultdict(list)
            for assessment in assessments:
                assessments_by_patient[assessment.get("patient_id")].append(assessment)
            
            sorted_patients = sorted(assessments_by_patient.items(), key=lambda x: max(a.get("risk_score", 0) for a in x[1]), reverse=True)
            
            for patient_id, patient_assessments in sorted_patients:
                patient = patients.get(patient_id, {})
                patient_name = patient.get("name", f"Patient {patient_id}")
                patient_age = patient.get("age")
                
                col_header, col_button = st.columns([4, 1])
                with col_header:
                    st.markdown(f"#### 👤 {patient_name} ({len(patient_assessments)} assessment{'s' if len(patient_assessments) > 1 else ''})")
                with col_button:
                    if st.button("➕ New Assessment", key=f"new_assess_{patient_id}", use_container_width=True):
                        with st.spinner(f"Creating new assessment for {patient_name}..."):
                            result = call_api(f"/assessment/{patient_id}", method="POST", timeout=60)
                        if result:
                            st.success(f"✅ New assessment created!")
                            st.rerun()
                        else:
                            st.error("Failed to create assessment.")
                
                patient_assessments_sorted = sorted(patient_assessments, key=lambda x: x.get("created_at", ""), reverse=True)
                
                for assessment in patient_assessments_sorted:
                    render_assessment_card(assessment, patient_name, patient_age, show_date=True)
                
                st.markdown("---")
    
    st.divider()
    if st.button("⬅ Back to Modules"):
        st.session_state.view = "category"
        st.session_state.selected_assessment_id = None
        st.rerun()
