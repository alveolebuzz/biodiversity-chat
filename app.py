import streamlit as st
import pandas as pd
import os, json
from google.cloud import bigquery
from openai import OpenAI

# ---- READ KEYS FROM STREAMLIT SECRETS ----
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
BIGQUERY_CREDS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")

# Load BigQuery credentials from Streamlit Secrets JSON
bq_client = bigquery.Client.from_service_account_info(json.loads(BIGQUERY_CREDS))

# Set up OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# ---- STREAMLIT UI ----
st.title("🌱 Biodiversity Data Chat")
st.write("Ask any question about your biodiversity data stored in BigQuery.")

# User input
question = st.text_input("Type your question here:")

if st.button("Ask") and question:
    st.write(f"**Your question:** {question}")

    # 1️⃣ Ask GPT to write SQL
    schema_hint = """
    The table is named `biodiversity_data` and may include columns like:
    building_name, city, date, pesticide, species, count, etc.
    """

    sql_prompt = f"""
You are a data assistant. 
The user will ask a question about biodiversity data in BigQuery. 

Rules:
- Only return a valid BigQuery **STANDARD SQL** query.
- Return ONLY the query — no explanations, no text like “Here’s the query.”
- Do NOT use triple backticks (```).
- Always query this table: `biodiversitychat.biodiversity.biodiversity_data`
    User question: {question}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": sql_prompt}],
        temperature=0
    )

    sql_code = response.choices[0].message.content.strip()
    st.code(sql_code, language="sql")

    # 2️⃣ Run the SQL query
    try:
        query_job = bq_client.query(sql_code)
        df = query_job.to_dataframe()

        # Show table in Streamlit
        st.subheader("📊 Query Results")
        st.dataframe(df)

        # 3️⃣ Summarize result with GPT
        summary_prompt = f"Summarize this table in plain English: {df.head(10).to_string()}"
        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0
        )
        summary = summary_response.choices[0].message.content

        st.subheader("📝 Summary")
        st.write(summary)

    except Exception as e:
        st.error(f"❌ There was an error running the query: {e}")

