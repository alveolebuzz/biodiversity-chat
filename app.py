import streamlit as st
import pandas as pd
import os, json
from google.cloud import bigquery
from openai import OpenAI

# ---- OPTIONAL WARNING IF MISSING DB-DTYPES ----
try:
    import db_dtypes
except ImportError:
    st.warning("⚠️ The package 'db-dtypes' is required for BigQuery pandas integration.")

# ---- CUSTOM CSS TO MAKE SEARCH BAR GOLD ----
st.markdown(
    """
    <style>
    div[data-baseweb="input"] > div {
        border-color: #DAA520 !important;   /* gold border by default */
    }
    div[data-baseweb="input"] > div:focus-within {
        box-shadow: 0 0 0 2px #FFD700 !important; /* gold glow when typing */
        border-color: #FFD700 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---- READ KEYS FROM STREAMLIT SECRETS ----
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
BIGQUERY_CREDS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")

# Load BigQuery credentials from Streamlit Secrets JSON
bq_client = bigquery.Client.from_service_account_info(json.loads(BIGQUERY_CREDS))

# ---- FETCH SCHEMA FOR GPT ----
table = bq_client.get_table("biodiversitychat.biodiversity.biodiversitychat_native")
columns = [schema.name for schema in table.schema]
column_types = {schema.name: schema.field_type for schema in table.schema}  # NEW: track types

# ---- OPENAI CLIENT ----
client = OpenAI(api_key=OPENAI_API_KEY)

# ---- STREAMLIT UI ----
st.title("🌱 Biodiversity Data Chat")
st.write("Ask any question about your biodiversity data stored in BigQuery.")

# Show available columns (for debugging)
st.sidebar.write("📋 Available columns:", columns)
st.sidebar.write("📂 Column types:", column_types)

# ---- USER INPUT ----
question = st.text_input("Type your question here:")

if st.button("Ask") and question:
    st.write(f"**Your question:** {question}")

    # ---- GPT PROMPT FOR SQL ----
    sql_prompt = f"""
You are a data assistant. 
The user will ask a question about biodiversity data in BigQuery. 

⚠️ Rules for writing SQL:
- Only return a valid BigQuery STANDARD SQL query.
- Return ONLY the query — no explanations, no comments, no Markdown.
- Do NOT use triple backticks (```).
- Always query this table exactly as written: `biodiversitychat.biodiversity.biodiversitychat_native`
- Only use these exact columns: {', '.join(columns)}
- Column data types: {column_types}
- When filtering, always match the correct type:
   • If the column is INT64, do NOT wrap the value in quotes.
   • If the column is STRING, wrap the value in single quotes.
- If the user asks about workshops, include BOTH the total number of workshops AND the workshop topics in the SQL output if columns like workshop1_topic, workshop2_topic, etc. exist.

User question: {question}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": sql_prompt}],
        temperature=0
    )

    # ---- CLEAN SQL ----
    sql_code = response.choices[0].message.content.strip()
    sql_code = sql_code.replace("```sql", "").replace("```", "").strip()
    st.code(sql_code, language="sql")

    # ---- RUN THE QUERY ----
    try:
        query_job = bq_client.query(sql_code)
        df = query_job.to_dataframe()

        # Show results table
        st.subheader("📊 Query Results")
        if df.empty:
            st.warning("⚠️ The query returned no data.")
        else:
            st.dataframe(df)

            # ---- GPT SUMMARY PROMPT ----
            summary_prompt = f"""
Here is the SQL query result:
{df.head(10).to_string()}

Please write a clear, human-friendly summary:
- State the total number of workshops if available.
- List the workshop topics (if present and not null).
- If there are no workshops or topics, say that clearly.
- Keep it short and professional.
"""

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

