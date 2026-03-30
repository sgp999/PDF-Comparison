from fastapi import FastAPI, UploadFile, File, HTTPException
from pypdf import PdfReader
from openai import OpenAI
from pypdf import PdfReader

import io

def extract_text(file):
    reader = PdfReader(file.file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

app = FastAPI()
client = OpenAI()

# ----------------------------
# Helpers
# ----------------------------

def validate_pdf(file: UploadFile):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"{file.filename} is not a PDF"
        )


def extract_text(file: UploadFile):
    try:
        pdf = PdfReader(io.BytesIO(file.file.read()))
        text = ""

        for page in pdf.pages:
            text += page.extract_text() or ""

        return text.strip()

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read PDF: {str(e)}"
        )


# 🔥 CHUNKING FUNCTION (REAL CODE — NOT IN QUOTES)
def chunk_text(text, chunk_size=2000, overlap=200):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return chunks


# 🔥 AI COMPARE (PROMPT IS STRING — THIS IS CORRECT)
def compare_with_ai(text1, text2):
    prompt = f"""
Compare these two insurance policies.

Return ONLY valid JSON in this format:

{{
  "summary": "...",
  "coverage_differences": ["...", "..."],
  "exclusions_differences": ["...", "..."],
  "limits_differences": ["...", "..."],
  "deductible_differences": ["...", "..."],
  "important_notes": ["...", "..."]
}}

Policy 1:
{text1}

Policy 2:
{text2}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text


# 🔥 COMPARE CHUNKS
def compare_chunks(chunks1, chunks2):
    results = []
    max_chunks = min(len(chunks1), len(chunks2))

    for i in range(max_chunks):
        result = compare_with_ai(chunks1[i], chunks2[i])
        results.append({
            "chunk": i + 1,
            "analysis": result
        })

    return results


# 🔥 FINAL SUMMARY
def summarize_results(results):
    combined = ""

    for r in results:
        combined += f"Chunk {r['chunk']}:\n{r['analysis']}\n\n"

    prompt = f"""
Summarize the overall differences between two insurance policies.

Return ONLY JSON:

{{
  "summary": "...",
  "coverage_differences": [],
  "exclusions_differences": [],
  "limits_differences": [],
  "deductible_differences": [],
  "important_notes": []
}}

Here are the chunk comparisons:
{combined[:12000]}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text


# ----------------------------
# Endpoints
# ----------------------------

@app.get("/")
async def root():
    return {"message": "API is running"}


@app.post("/compare")
async def compare_pdfs(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    validate_pdf(file1)
    validate_pdf(file2)

    text1 = extract_text(file1)
    text2 = extract_text(file2)

    if not text1:
        raise HTTPException(status_code=400, detail="No readable text in file1")

    if not text2:
        raise HTTPException(status_code=400, detail="No readable text in file2")

    # 🔥 Chunk both documents
    chunks1 = chunk_text(text1)
    chunks2 = chunk_text(text2)

    # 🔥 Compare chunks
    chunk_results = compare_chunks(chunks1, chunks2)

    # 🔥 Final summary
    final_analysis = summarize_results(chunk_results)

    return {
    "file1": file1.filename,
    "file2": file2.filename,
    "file1_chars": len(text1),
    "file2_chars": len(text2),
    "preview1": text1[:300],
    "preview2": text2[:300]
}