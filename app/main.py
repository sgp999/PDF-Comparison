import streamlit as st
from pypdf import PdfReader
from openai import OpenAI
import os

from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Page setup
st.set_page_config(page_title="PDF Comparison", layout="wide")

# Clean UI
st.markdown(
    """
    <style>
        header {visibility: hidden;}
        .block-container {
            padding-top: 0rem;
            padding-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_text(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text()
    return text


def compare_policies(text1, text2):
    prompt = f"""
You are an insurance expert.

Compare these two insurance policies and return:

1. Plan Name
2. Premium
3. Deductible
4. Out-of-pocket max
5. Key differences
6. Which is better and why

Policy 1:
{text1[:4000]}

Policy 2:
{text2[:4000]}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )

    return response.output[0].content[0].text


# UI
st.markdown(
    "<h1 style='margin-top:0;'>PDF Insurance Policy Comparison</h1>",
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)

with col1:
    file1 = st.file_uploader("Upload Policy 1", type=["pdf"])

with col2:
    file2 = st.file_uploader("Upload Policy 2", type=["pdf"])

if st.button("Compare Policies"):
    if not file1 or not file2:
        st.warning("Please upload both PDF files.")
    else:
        with st.spinner("Extracting text..."):
            text1 = extract_text(file1)
            text2 = extract_text(file2)

        with st.spinner("Analyzing with AI..."):
            result = compare_policies(text1, text2)

        st.subheader("Comparison Result")
        st.write(result)

        # Download button
        st.download_button(
            label="Download Comparison",
            data=result,
            file_name="policy_comparison.txt",
        )