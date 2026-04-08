from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pypdf import PdfReader
from openpyxl import Workbook
from openai import OpenAI
from dotenv import load_dotenv
import os
import uuid
import json

# -----------------------------
# Setup
# -----------------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()


# -----------------------------
# Extract text from PDF
# -----------------------------
def extract_text_from_pdf(upload_file: UploadFile) -> str:
    try:
        reader = PdfReader(upload_file.file)
        text = ""

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        return text.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading PDF: {str(e)}")


# -----------------------------
# AI Extraction
# -----------------------------
def extract_insurance_data(text):
    prompt = f"""
You are an expert at reading health insurance policies.

Extract structured data from the text below.

Return ONLY valid JSON. No explanation.

Rules:
- If a value is not found, return "N/A"
- Keep dollar amounts exactly as written (e.g. $45, $1,000, $250 per visit)
- Do not guess values
- Prefer numbers over descriptions
- If multiple values exist, choose the most common / standard one

Fields:
- plan_name
- premium
- deductible_individual
- deductible_family
- out_of_pocket_max_individual
- out_of_pocket_max_family
- primary_care
- specialist
- urgent_care
- emergency_room
- hospital_stay
- outpatient_surgery
- diagnostic_test
- imaging
- lab_work
- preventive_care
- mental_health_outpatient
- mental_health_inpatient
- physical_therapy
- ambulance
- generic_drugs
- preferred_brand_drugs

Text:
{text[:8000]}
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    try:
        raw = response.output[0].content[0].text
        return json.loads(raw)
    except:
        return {}


# -----------------------------
# Build comparison table
# -----------------------------
def build_comparison_rows(data1, data2):
    fields = [
        ("Plan Name", "plan_name"),
        ("Premium", "premium"),
        ("Deductible (Individual)", "deductible_individual"),
        ("Deductible (Family)", "deductible_family"),
        ("Out of Pocket Max (Individual)", "out_of_pocket_max_individual"),
        ("Out of Pocket Max (Family)", "out_of_pocket_max_family"),
        ("Primary Care", "primary_care"),
        ("Specialist", "specialist"),
        ("Urgent Care", "urgent_care"),
        ("Emergency Room", "emergency_room"),
        ("Hospital Stay", "hospital_stay"),
        ("Outpatient Surgery", "outpatient_surgery"),
        ("Diagnostic Test", "diagnostic_test"),
        ("Imaging", "imaging"),
        ("Lab Work", "lab_work"),
        ("Preventive Care", "preventive_care"),
        ("Mental Health (Outpatient)", "mental_health_outpatient"),
        ("Mental Health (Inpatient)", "mental_health_inpatient"),
        ("Physical Therapy", "physical_therapy"),
        ("Ambulance", "ambulance"),
        ("Generic Drugs", "generic_drugs"),
        ("Preferred Brand Drugs", "preferred_brand_drugs"),
    ]

    rows = []

    for label, key in fields:
        rows.append({
            "Field": label,
            "Policy 1": data1.get(key, "N/A"),
            "Policy 2": data2.get(key, "N/A")
        })

    return rows


# -----------------------------
# Save Excel
# -----------------------------
def save_to_excel(rows, output_path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Comparison Results"

    ws.append(["Field", "Policy 1", "Policy 2"])

    for row in rows:
        ws.append([
            row.get("Field", ""),
            row.get("Policy 1", ""),
            row.get("Policy 2", "")
        ])

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 35
    ws.column_dimensions["C"].width = 35

    wb.save(output_path)


# -----------------------------
# Home
# -----------------------------
@app.get("/")
def root():
    return {"message": "API is running"}


# -----------------------------
# UI page
# -----------------------------
@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
    <html>
        <head>
            <title>PDF Comparison Tool</title>
        </head>
        <body>
            <h2>Compare Insurance PDFs</h2>

            <form action="/compare" enctype="multipart/form-data" method="post">
                <label>Policy 1 PDF:</label><br>
                <input type="file" name="file1" accept=".pdf"><br><br>

                <label>Policy 2 PDF:</label><br>
                <input type="file" name="file2" accept=".pdf"><br><br>

                <button type="submit">Compare Files</button>
            </form>
        </body>
    </html>
    """


# -----------------------------
# Compare route
# -----------------------------
@app.post("/compare", response_class=HTMLResponse)
async def compare_pdfs(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    if not file1.filename.lower().endswith(".pdf") or not file2.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Both files must be PDFs.")

    text1 = extract_text_from_pdf(file1)
    file1.file.seek(0)

    text2 = extract_text_from_pdf(file2)
    file2.file.seek(0)

    # AI extraction
    data1 = extract_insurance_data(text1)
    data2 = extract_insurance_data(text2)

    comparison_rows = build_comparison_rows(data1, data2)

    os.makedirs("exports", exist_ok=True)

    file_id = str(uuid.uuid4())
    output_path = os.path.join("exports", f"{file_id}.xlsx")

    save_to_excel(comparison_rows, output_path)

    table_rows = ""
    for row in comparison_rows:
        table_rows += f"""
        <tr>
            <td>{row.get("Field", "")}</td>
            <td>{row.get("Policy 1", "")}</td>
            <td>{row.get("Policy 2", "")}</td>
        </tr>
        """

    return f"""
    <html>
        <head>
            <title>Comparison Results</title>
        </head>
        <body>
            <h2>Comparison Results</h2>

            <table border="1" cellpadding="8" cellspacing="0">
                <tr>
                    <th>Field</th>
                    <th>Policy 1</th>
                    <th>Policy 2</th>
                </tr>
                {table_rows}
            </table>

            <br>
            <a href="/download/{file_id}">
                <button>Save to Excel</button>
            </a>

            <br><br>
            <a href="/ui">Compare another pair of PDFs</a>
        </body>
    </html>
    """


# -----------------------------
# Download Excel
# -----------------------------
@app.get("/download/{file_id}")
def download_file(file_id: str):
    file_path = os.path.join("exports", f"{file_id}.xlsx")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(
        path=file_path,
        filename="comparison_results.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )