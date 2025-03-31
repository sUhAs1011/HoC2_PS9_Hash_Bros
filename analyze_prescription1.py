from flask import request, jsonify, current_app
import os
from pdf2image import convert_from_path
from PIL import Image
import ollama
import json
from google import genai
from google.genai import types
import io

# Gemini API Configuration
client = genai.Client(api_key="AIzaSyD6C1dYpg-k_ZLiaPuonL9OrCkr5UKjsfw")  # Replace with your API key

def extract_text_from_image(image_path):
    """Extracts drug names from an image using Gemini API."""
    try:
        print(f"Image Path: {image_path}")
        print(f"Type of image_path: {type(image_path)}")

        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        byte_stream = io.BytesIO(image_bytes)
        print(f"Type of byte_stream: {type(byte_stream)}")
        image = Image.open(byte_stream)
        print("Image opened successfully.")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[image, "Extract the drug names and dosages from this prescription. If no dosages are present, mention that. Return the results in a json like format. Example: [{'drug':'drugname', 'dosage':'dosage'},...]"]
        )
        return response.text
    except Exception as e:
        return f"Gemini API Error: {e}"

def extract_text_from_pdf(pdf_path):
    """Placeholder for PDF extraction. Using Gemini API would be more efficient here too."""
    try:
        images = convert_from_path(pdf_path)
        text = "\n".join([str(img) for img in images]) #This is a placeholder, as OCR on pdfs is complex.
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {e}"

def analyze_ddi_ollama(extracted_drugs, ddi_data):
    """Analyzes drug-drug interactions using Ollama."""
    if ddi_data is None:
        return "Error: Drug interaction data not available."
    try:
        prompt = f"""
        Drug list from prescription: {extracted_drugs}.
        Drug-Drug Interaction dataset:\n{ddi_data}\n
        IMPORTANT: Analyze the drug interactions ONLY based on the drugs provided in the prescription drug list.
        Provide a summary of any severe interactions, and provide alternative medications if applicable.
        """
        response = ollama.chat(
            model='llama2',  # Use the model you downloaded
            messages=[
                {
                    'role': 'user',
                    'content': prompt,
                },
            ],
        )
        return response['message']['content']
    except Exception as e:
        return f"Ollama DDI Error: {e}"

def upload_prescription():
    """Handles prescription upload, OCR, and DDI analysis."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        patient_id = request.form.get("patient_id")
        timestamp = request.form.get("timestamp")

        if not all([patient_id, timestamp]):
            return jsonify({"error": "Missing required fields"}), 400

        filepath = os.path.join("uploads", file.filename)
        file.save(filepath)

        extracted_text = ""
        if file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            extracted_text = extract_text_from_image(filepath)
            print(f"Gemini Response: {extracted_text}")
        elif file.filename.lower().endswith(".pdf"):
            extracted_text = extract_text_from_pdf(filepath) #Placeholder.

        os.remove(filepath)

        if not extracted_text:
            return jsonify({"error": "Failed to extract text from the file."}), 400

        ddi_analysis_result = analyze_ddi_ollama(extracted_text, current_app.ddi_data)

        return jsonify({
            "Extracted_Text": extracted_text,
            "DDI Analysis": ddi_analysis_result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500