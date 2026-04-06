from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from pypdf import PdfReader
from dotenv import load_dotenv
from openai import OpenAI
import os
import json
import html

load_dotenv()

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.get("/")
def root():
    return {"message": "API is running"}


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
    <html>
        <head>
            <title>PDF Comparison Tool</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: #f4f7fb;
                    color: #1f2937;
                    margin: 0;
                    padding: 0;
                }
                .container {
                    max-width: 1000px;
                    margin: 40px auto;
                    background: white;
                    border-radius: 14px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                    overflow: hidden;
                }
                .header {
                    background: linear-gradient(135deg, #16324f, #1f5b8f);
                    color: white;
                    padding: 32px;
                }
                .header h1 {
                    margin: 0 0 8px 0;
                    font-size: 32px;
                }
                .header p {
                    margin: 0;
                    opacity: 0.95;
                }
                .content {
                    padding: 32px;
                }
                .upload-box {
                    border: 2px dashed #cbd5e1;
                    border-radius: 12px;
                    padding: 24px;
                    background: #f8fafc;
                }
                .field {
                    margin-bottom: 18px;
                }
                label {
                    display: block;
                    margin-bottom: 8px;
                    font-weight: bold;
                }
                input[type="file"] {
                    width: 100%;
                    padding: 10px;
                    background: white;
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                }
                button {
                    background: #1f5b8f;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 12px 20px;
                    font-size: 16px;
                    cursor: pointer;
                }
                button:hover {
                    background: #16324f;
                }
                .note {
                    margin-top: 14px;
                    color: #6b7280;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>PDF Comparison Tool</h1>
                    <p>Upload two insurance policy PDFs to generate a side-by-side comparison.</p>
                </div>
                <div class="content">
                    <form action="/compare" method="post" enctype="multipart/form-data" class="upload-box">
                        <div class="field">
                            <label for="file1">Policy PDF 1</label>
                            <input type="file" name="file1" id="file1" accept=".pdf" required>
                        </div>

                        <div class="field">
                            <label for="file2">Policy PDF 2</label>
                            <input type="file" name="file2" id="file2" accept=".pdf" required>
                        </div>

                        <button type="submit">Compare Policies</button>
                        <div class="note">This version compares key costs and coverage fields side by side.</div>
                    </form>
                </div>
            </div>
        </body>
    </html>
    """


def extract_text(file):
    reader = PdfReader(file.file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
        text += "\n"
    return text


def extract_cost_summary(policy_text: str, label: str) -> dict:
    prompt = f"""
You are extracting insurance benefit information from a policy document.

Return only valid JSON.
Do not include markdown fences.
Do not include explanation.

Extract these fields if present. For each field, capture the cost or percent coverage exactly as stated.

If not found, use "Not found".

Return JSON in this format:
{{
  "plan_name": "",
  "premium": "",
  "deductible_individual": "",
  "deductible_family": "",
  "out_of_pocket_max_individual": "",
  "out_of_pocket_max_family": "",
  "primary_care": "",
  "specialist": "",
  "urgent_care": "",
  "emergency_room": "",
  "hospital_stay": "",
  "outpatient_surgery": "",
  "diagnostic_test": "",
  "imaging": "",
  "lab_work": "",
  "preventive_care": "",
  "mental_health_outpatient": "",
  "mental_health_inpatient": "",
  "physical_therapy": "",
  "ambulance": "",
  "generic_drugs": "",
  "preferred_brand_drugs": "",
  "nonpreferred_brand_drugs": "",
  "specialty_drugs": "",
  "coverage_notes": "",
  "short_notes": ""
}}

Policy label: {label}

Policy text:
{policy_text[:20000]}
"""
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    raw = (response.output_text or "").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def build_summary(p1, p2):
    prompt = f"""
Compare these two insurance policies.

Policy 1:
{json.dumps(p1, indent=2)}

Policy 2:
{json.dumps(p2, indent=2)}

Write 5 to 7 concise bullet points covering:
- premium differences
- deductible differences
- out-of-pocket differences
- doctor visit differences
- drug coverage differences
- major takeaways
"""
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )
    return (response.output_text or "").strip()


def render_row(label, key, p1, p2):
    v1 = str(p1.get(key, "Not found"))
    v2 = str(p2.get(key, "Not found"))
    return f"""
    <tr>
        <td>{html.escape(label)}</td>
        <td>{html.escape(v1)}</td>
        <td>{html.escape(v2)}</td>
    </tr>
    """


@app.post("/compare", response_class=HTMLResponse)
async def compare(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    try:
        text1 = extract_text(file1)
        text2 = extract_text(file2)

        p1 = extract_cost_summary(text1, file1.filename or "Policy 1")
        p2 = extract_cost_summary(text2, file2.filename or "Policy 2")

        summary = build_summary(p1, p2)

    except Exception as e:
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px;">
                <h2>Error</h2>
                <p>{html.escape(str(e))}</p>
                <p><a href="/ui">Back to upload page</a></p>
            </body>
        </html>
        """

    general_rows = "".join([
        render_row("Plan Name", "plan_name", p1, p2),
        render_row("Premium", "premium", p1, p2),
        render_row("Deductible - Individual", "deductible_individual", p1, p2),
        render_row("Deductible - Family", "deductible_family", p1, p2),
        render_row("Out-of-Pocket Max - Individual", "out_of_pocket_max_individual", p1, p2),
        render_row("Out-of-Pocket Max - Family", "out_of_pocket_max_family", p1, p2),
    ])

    medical_rows = "".join([
        render_row("Primary Care", "primary_care", p1, p2),
        render_row("Specialist", "specialist", p1, p2),
        render_row("Urgent Care", "urgent_care", p1, p2),
        render_row("Emergency Room", "emergency_room", p1, p2),
        render_row("Hospital Stay", "hospital_stay", p1, p2),
        render_row("Outpatient Surgery", "outpatient_surgery", p1, p2),
        render_row("Diagnostic Test", "diagnostic_test", p1, p2),
        render_row("Imaging", "imaging", p1, p2),
        render_row("Lab Work", "lab_work", p1, p2),
        render_row("Preventive Care", "preventive_care", p1, p2),
        render_row("Mental Health - Outpatient", "mental_health_outpatient", p1, p2),
        render_row("Mental Health - Inpatient", "mental_health_inpatient", p1, p2),
        render_row("Physical Therapy", "physical_therapy", p1, p2),
        render_row("Ambulance", "ambulance", p1, p2),
    ])

    drug_rows = "".join([
        render_row("Generic Drugs", "generic_drugs", p1, p2),
        render_row("Preferred Brand Drugs", "preferred_brand_drugs", p1, p2),
        render_row("Nonpreferred Brand Drugs", "nonpreferred_brand_drugs", p1, p2),
        render_row("Specialty Drugs", "specialty_drugs", p1, p2),
    ])

    note_rows = "".join([
        render_row("Coverage Notes", "coverage_notes", p1, p2),
        render_row("Short Notes", "short_notes", p1, p2),
    ])

    return f"""
    <html>
        <head>
            <title>Comparison Results</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: #f4f7fb;
                    color: #1f2937;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 1150px;
                    margin: 30px auto;
                    background: white;
                    border-radius: 14px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #16324f, #1f5b8f);
                    color: white;
                    padding: 28px 32px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}
                .sub {{
                    margin-top: 8px;
                    opacity: 0.95;
                    font-size: 14px;
                }}
                .content {{
                    padding: 28px 32px 40px 32px;
                }}
                .summary {{
                    background: #f8fafc;
                    border: 1px solid #dbe4ee;
                    border-radius: 12px;
                    padding: 18px;
                    white-space: pre-wrap;
                    margin-bottom: 28px;
                }}
                h2 {{
                    margin-top: 28px;
                    margin-bottom: 12px;
                    font-size: 20px;
                    color: #16324f;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 24px;
                    overflow: hidden;
                    border-radius: 10px;
                }}
                th, td {{
                    border: 1px solid #dbe4ee;
                    padding: 10px 12px;
                    text-align: left;
                    vertical-align: top;
                }}
                th {{
                    background: #eef4fa;
                }}
                tr:nth-child(even) td {{
                    background: #fafcff;
                }}
                .back-link {{
                    display: inline-block;
                    margin-top: 12px;
                    text-decoration: none;
                    color: #1f5b8f;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Side-by-Side Policy Comparison</h1>
                    <div class="sub">
                        <strong>Policy 1:</strong> {html.escape(file1.filename or "Policy 1")} &nbsp;&nbsp;|&nbsp;&nbsp;
                        <strong>Policy 2:</strong> {html.escape(file2.filename or "Policy 2")}
                    </div>
                </div>

                <div class="content">
                    <h2>Summary</h2>
                    <div class="summary">{html.escape(summary)}</div>

                    <h2>General Plan Costs</h2>
                    <table>
                        <tr>
                            <th>Item</th>
                            <th>{html.escape(file1.filename or "Policy 1")}</th>
                            <th>{html.escape(file2.filename or "Policy 2")}</th>
                        </tr>
                        {general_rows}
                    </table>

                    <h2>Medical Benefits</h2>
                    <table>
                        <tr>
                            <th>Item</th>
                            <th>{html.escape(file1.filename or "Policy 1")}</th>
                            <th>{html.escape(file2.filename or "Policy 2")}</th>
                        </tr>
                        {medical_rows}
                    </table>

                    <h2>Drug Coverage</h2>
                    <table>
                        <tr>
                            <th>Item</th>
                            <th>{html.escape(file1.filename or "Policy 1")}</th>
                            <th>{html.escape(file2.filename or "Policy 2")}</th>
                        </tr>
                        {drug_rows}
                    </table>

                    <h2>Notes</h2>
                    <table>
                        <tr>
                            <th>Item</th>
                            <th>{html.escape(file1.filename or "Policy 1")}</th>
                            <th>{html.escape(file2.filename or "Policy 2")}</th>
                        </tr>
                        {note_rows}
                    </table>

                    <a class="back-link" href="/ui">← Compare another pair</a>
                </div>
            </div>
        </body>
    </html>
    """