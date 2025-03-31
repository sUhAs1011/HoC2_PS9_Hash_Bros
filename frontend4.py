import streamlit as st
import requests
import json

# API Base URL
BACKEND_URL = "http://127.0.0.1:5000"

st.set_page_config(page_title="Doctor Portal", layout="wide")

# Session Management
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "doctor_id" not in st.session_state:
    st.session_state.doctor_id = None

# Sidebar Navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Login", "Upload Prescription", "View Reports", "Dashboard", "Patient Risk Profile"])

# 👨‍⚕️ Login Page
if page == "Login":
    st.title("Doctor Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        response = requests.post(f"{BACKEND_URL}/login", json={"username": username, "password": password})
        if response.status_code == 200:
            data = response.json()
            st.session_state.access_token = data["access_token"]
            st.session_state.doctor_id = data["doctor_id"]
            st.success("✅ Logged in successfully!")
        else:
            st.error("❌ Invalid credentials")

# 📤 Upload Prescription
elif page == "Upload Prescription":
    if not st.session_state.access_token:
        st.warning("⚠ Please log in first.")
    else:
        st.title("Upload Prescription")
        uploaded_file = st.file_uploader("Upload a prescription", type=["pdf", "png", "jpg"])
        patient_id = st.text_input("Patient ID")
        timestamp = st.text_input("Timestamp")

        if uploaded_file and st.button("Submit"):
            patient_id = patient_id.strip() if patient_id else ""

            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            data = {"patient_id": patient_id, "timestamp": timestamp}
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}

            response = requests.post(f"{BACKEND_URL}/upload_prescription", files=files, data=data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                st.success(f"✅ Prescription processed successfully!")
                st.write("### Extracted Text:")
                st.write(result.get('Extracted_Text'))
                st.write("### DDI Analysis:")
                st.write(result.get("DDI Analysis"))
            else:
                st.error("❌ Failed to process prescription!")

# 📄 View Reports
elif page == "View Reports":
    if not st.session_state.access_token:
        st.warning("⚠ Please log in first.")
    else:
        st.title("📄 View Reports")
        patient_id = st.text_input("Enter Patient ID to view reports:")
        if st.button("Get Reports") and patient_id:
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            response = requests.get(f"{BACKEND_URL}/get_prescriptions/{patient_id}", headers=headers)
            if response.status_code == 200:
                reports = response.json().get("result", [])
                if reports:
                    st.write("### Reports:")
                    for report in reports:
                        data = json.loads(bytes.fromhex(report["data"]).decode())
                        st.write(f"Timestamp: {data.get('timestamp')}")
                        st.markdown(f"IPFS Link: [View on IPFS](https://ipfs.io/ipfs/{data.get('cid')})")
                        st.write(f"DDI Analysis: {data.get('ddi_analysis')}") #Display the ddi_analysis
                        st.write("---")
                else:
                    st.info("No reports found for this patient.")
            else:
                st.error("❌ Failed to fetch reports.")

# 📊 Dashboard Page
elif page == "Dashboard":
    if not st.session_state.access_token:
        st.warning("⚠ Please log in first.")
    else:
        st.title("📊 Doctor's Dashboard")

        headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
        response = requests.get(f"{BACKEND_URL}/dashboard", headers=headers)

        if response.status_code == 200:
            uploads = response.json().get("uploads", [])

            if not uploads:
                st.info("No uploads found.")
            else:
                st.write("### Uploaded Prescriptions")
                for upload in uploads:
                    st.write(f"🧑‍⚕️ **Patient ID:** `{upload['Patient_ID']}`")
                    st.markdown(f"📄 **File:** [View on IPFS](https://ipfs.io/ipfs/{upload['CID']})")
                    st.write(f"🕒 **Uploaded on:** {upload['Timestamp']}")
                    st.write("---")
        else:
            st.error("❌ Failed to fetch dashboard data!")

if st.sidebar.button("Logout"):
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    requests.post(f"{BACKEND_URL}/logout", headers=headers)
    st.session_state.access_token = None
    st.session_state.doctor_id = None
    st.success("✅ Logged out successfully! Redirecting...")
    st.rerun()

elif page == "Patient Risk Profile":
    if not st.session_state.access_token:
        st.warning("⚠ Please log in first.")
    else:
        st.title("Patient Risk Profile")
        patient_id = st.text_input("Enter Patient ID to generate risk profile:")
        if st.button("Generate Risk Profile") and patient_id:
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            response = requests.get(f"{BACKEND_URL}/generate_patient_risk_profile/{patient_id}", headers=headers)
            if response.status_code == 200:
                risk_profile = response.json().get("risk_profile")
                st.write("### Patient Risk Profile:")
                st.write(risk_profile)
            else:
                st.error("❌ Failed to generate risk profile.")
