import streamlit as st

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
        c1.metric("Patients", "12,500")
        c2.metric("Medicines", "8,900")
        c3.metric("Assessments", "6,400")
    
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
                "Column Name": ["medication_id", "name", "salt", "atc_code", "therapeutic_class", "min_age", "max_age", "age_warning_above/below", "contraindicated_diseases"],
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
FROM Patient p
JOIN Polypharmacy_Assessment pa ON p.patient_id = pa.patient_id
WHERE pa.risk_score > 75
ORDER BY pa.risk_score DESC;
        """, language="sql")
        
        st.subheader("2. Find Medicines with Age Warnings")
        st.code("""
SELECT m.name, m.min_age, m.max_age, p.name, p.age
FROM Patient p
JOIN Medicine m ON FIND_IN_SET(m.medication_id, p.medications)
WHERE (p.age < m.min_age OR p.age > m.max_age);
        """, language="sql")
        
        if st.button("▶️ Execute Queries"):
            st.success("Queries executed successfully! 145 rows returned.")

    elif tab == "⚡ Triggers":
        st.markdown("### Database Triggers")
        
        st.subheader("Trigger: Auto-Generate Risk Assessment")
        st.code("""
CREATE TRIGGER after_patient_update
AFTER UPDATE ON Patient
FOR EACH ROW
BEGIN
    -- Simplified logic: Insert assessment if meds changed
    IF OLD.medications <> NEW.medications THEN
        INSERT INTO Polypharmacy_Assessment (patient_id, total_active_meds, risk_score)
        VALUES (NEW.patient_id, 
                LENGTH(NEW.medications) - LENGTH(REPLACE(NEW.medications, ',', '')) + 1,
                (LENGTH(NEW.medications) - LENGTH(REPLACE(NEW.medications, ',', '')) + 1) * 5
        );
    END IF;
END;
        """, language="sql")

    elif tab == "📊 Output":
        st.markdown("### Module Output")
        
        # Patient Header
        st.success("✅ **Risk Assessment Completed**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
             st.info("📋 **Patient ID:** PT-2024-001234")
        with col2:
             st.info("👤 **Name:** John Doe")
        with col3:
             st.info("📅 **Age:** 78 Years")

        st.divider()

        # Risk Score Section
        st.markdown("#### ⚠️ Risk Analysis")
        risk_col1, risk_col2, risk_col3 = st.columns(3)
        
        with risk_col1:
            st.metric(label="Risk Score", value="85 / 100", delta="High Risk", delta_color="inverse")
        with risk_col2:
            st.metric(label="Active Medications", value="12", delta="+2 (New)")
        with risk_col3:
            st.metric(label="Duplicate Therapies", value="1", delta="Action Required", delta_color="inverse")

        st.divider()

        # Detailed Findings
        c1, c2 = st.columns(2)
        
        with c1:
            st.warning("#### 🚫 Duplicate Therapy Detected")
            st.write("**Medications:** Aspirin + Clopidogrel")
            st.write("**Category:** Anticoagulants")
            st.write("**Recommendation:** Review for bleeding risk. Consider consolidating.")

        with c2:
            st.error("#### 👴 Age-Based Warning (Beers Criteria)")
            st.write("**Medication:** Diazepam")
            st.write("**Reason:** Not recommended for patients > 65 years due to increased fall risk.")
            st.write("**Action:** Deprescribe or switch to safer alternative.")
            
        st.divider()