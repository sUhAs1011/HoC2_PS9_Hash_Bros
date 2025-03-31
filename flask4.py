from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
import ollama 
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
)
import requests
import sys
import traceback
import os
import json
import binascii
from datetime import timedelta
from backend.api.controllers.analyze_prescription1 import upload_prescription, extract_text_from_image, extract_text_from_pdf, analyze_ddi_ollama  # Import from analyze_prescription.py

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configure JWT
app.config["JWT_SECRET_KEY"] = "supersecretjwtkey"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)

# IPFS & MultiChain Configuration
RPC_USER = "multichainrpc"
RPC_PASSWORD = "GAVoYuuNd2BNwPfoFYzU73Xk71T3ZzKMp178AgwkBqay"
RPC_PORT = "8362"
NODE_IP = "127.0.0.1"
CHAIN_NAME = "ehr-blockchain"

BASE_URL = f"http://{RPC_USER}:{RPC_PASSWORD}@{NODE_IP}:{RPC_PORT}/"
IPFS_API_URL = "http://127.0.0.1:5001/api/v0/add"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Dummy doctor credentials (Replace with DB authentication)
DOCTORS = {
    "doctor1": {"password": "pass123", "doctor_id": "D001"},
    "doctor2": {"password": "pass456", "doctor_id": "D002"},
}

# Load DDI dataset from JSON
try:
    with open(r"C:\Users\NITRO\OneDrive\Desktop\healthchain\backend\ai\datasets\drug_interactions.json", 'r') as file:  # Update your path!
        app.ddi_data = json.load(file)
except FileNotFoundError:
    app.ddi_data = None
    print("Error: drug_interactions.json not found.")
except json.JSONDecodeError:
    app.ddi_data = None
    print("Error: Invalid JSON format in drug_interactions.json.")

# Function to interact with MultiChain RPC API
def multichain_request(method, params=[]):
    payload = {"method": method, "params": params, "id": 1, "jsonrpc": "2.0"}
    try:
        response = requests.post(BASE_URL, json=payload)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"MultiChain RPC request failed: {str(e)}"}

# Upload file to IPFS
def upload_to_ipfs(filepath):
    try:
        with open(filepath, "rb") as f:
            files = {"file": f}
            response = requests.post(IPFS_API_URL, files=files)
            ipfs_response = response.json()
            return ipfs_response.get("Hash")
    except requests.exceptions.RequestException as e:
        return {"error": f"IPFS upload failed: {str(e)}"}

# Convert JSON to Hexadecimal (Required by MultiChain)
def json_to_hex(data):
    json_string = json.dumps(data)
    return binascii.hexlify(json_string.encode()).decode()

# 👨‍⚕️ Login - Generate JWT
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if username in DOCTORS and DOCTORS[username]["password"] == password:
        doctor_id = DOCTORS[username]["doctor_id"]
        access_token = create_access_token(identity=doctor_id)
        return jsonify({"message": "Login successful", "access_token": access_token, "doctor_id": doctor_id})

    return jsonify({"error": "Invalid credentials"}), 401

# 📤 Upload Prescription (Protected)
@app.route("/upload_prescription", methods=["POST"])
@jwt_required()
def upload_prescription_route():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        patient_id = request.form.get("patient_id")
        timestamp = request.form.get("timestamp")
        doctor_id = get_jwt_identity()

        if not all([patient_id, timestamp, doctor_id]):
            return jsonify({"error": "Missing required fields"}), 400

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        cid = upload_to_ipfs(filepath)
        if isinstance(cid, dict) and "error" in cid:
            return jsonify(cid), 500

        extracted_text = ""
        if file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            extracted_text = extract_text_from_image(filepath)
        elif file.filename.lower().endswith(".pdf"):
            extracted_text = extract_text_from_pdf(filepath)

        os.remove(filepath)

        if not extracted_text:
            return jsonify({"error": "Failed to extract text from the file."}), 400

        ddi_analysis_result = analyze_ddi_ollama(extracted_text, current_app.ddi_data)

        data = {"cid": cid, "doctor_id": doctor_id, "timestamp": timestamp, "extracted_text": extracted_text, "ddi_analysis": ddi_analysis_result}
        hex_data = json_to_hex(data)

        result = multichain_request("publish", ["prescription_data", patient_id, hex_data])

        return jsonify({
            "CID": cid,
            "Blockchain Response": result,
            "Extracted_Text": extracted_text,
            "DDI Analysis": ddi_analysis_result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 📄 Fetch Patient Prescriptions (Protected)
@app.route("/get_prescriptions/<patient_id>", methods=["GET"])
@jwt_required()
def get_prescriptions(patient_id):
    print(f"Fetching prescriptions for patient: {patient_id}")  # Debugging
    result = multichain_request("liststreamkeyitems", ["prescription_data", patient_id])
    print(f"MultiChain Result: {result}")  # Debugging
    return jsonify(result)

# 📊 Doctor Dashboard (Protected)
@app.route("/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    doctor_id = get_jwt_identity()
    result = multichain_request("liststreamitems", ["prescription_data"])

    print("📌 Raw Blockchain Response:", result)

    uploads = []
    for item in result.get("result", []):
        try:
            data = json.loads(bytes.fromhex(item["data"]).decode())
            print(f"📌 Decoded Data: {data}")

            patient_id = item.get("keys")[0] if item.get("keys") else None
            print(f"📌 Extracted Patient ID: {patient_id}")

            if data.get("doctor_id") == doctor_id:
                uploads.append({
                    "CID": data.get("cid"),
                    "Timestamp": data.get("timestamp"),
                    "Patient_ID": patient_id,
                    "IPFS_Link": f"https://ipfs.io/ipfs/{data.get('cid')}"
                })
        except (ValueError, KeyError) as e:
            print(f"🚨 Error processing item: {e}")

    return jsonify({"uploads": uploads})

BLACKLISTED_TOKENS = set()

@app.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    BLACKLISTED_TOKENS.add(jti)
    return jsonify({"message": "Logged out successfully!"})

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    return jwt_payload["jti"] in BLACKLISTED_TOKENS

@app.route("/generate_patient_risk_profile/<patient_id>", methods=["GET"])
@jwt_required()
def generate_patient_risk_profile(patient_id):
    try:
        # Retrieve all prescriptions for the patient
        print(f"Generating risk profile for patient: {patient_id}")
        result = multichain_request("liststreamkeyitems", ["prescription_data", patient_id])
        if "error" in result:
            return jsonify({"error": "Failed to retrieve prescriptions"}), 500

        reports = result.get("result", [])
        combined_drug_list = []
        for report in reports:
            data = json.loads(bytes.fromhex(report["data"]).decode())
            extracted_text = data.get("extracted_text", "")
            # Extract drug names from extracted text (you might need more robust parsing)
            # This is a basic example, refine as needed
            drugs = [word for word in extracted_text.split() if word.isalpha()]
            combined_drug_list.extend(drugs)

        # Perform cross-prescription DDI analysis
        ddi_analysis_result = analyze_ddi_ollama(combined_drug_list, current_app.ddi_data)


        # LLM risk profile generation
        prompt = f"""
            Patient's combined medications from past prescriptions: {combined_drug_list}
            Drug-Drug Interaction Analysis of combined medications: {ddi_analysis_result}
            Generate a patient risk profile focusing on potential drug-drug interaction side effects, considering all the patient's past prescriptions. Provide a summary of the most significant risks.
        """
        print(f"Combined drug list: {combined_drug_list}")
        print(f"DDI Analysis result: {ddi_analysis_result}")
        print(f"Ollama prompt: {prompt}")

        risk_profile = ollama.chat(model='llama2', messages=[{'role': 'user', 'content': prompt}])['message']['content']

        return jsonify({"risk_profile": risk_profile})

    except Exception as e:
        print(f"Error generating risk profile: {e}", file=sys.stderr)  # Print to stderr
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()  # Force flush
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)