# # frontend.py
# import streamlit as st
# import requests # To send HTTP requests to the backend
# import os

# # --- Configuration ---
# # Get the backend URL from environment variable or use default
# # This allows flexibility if your backend runs elsewhere
# BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/query")

# st.set_page_config(page_title="SQL Query Assistant", layout="wide")

# st.title("📊 SQL Query Assistant")
# st.caption("Ask a question about your data in natural language.")

# # --- User Input ---
# user_question = st.text_area("Enter your question here:", height=100)

# # --- Submit Button and Processing ---
# if st.button("Get Answer"):
#     if user_question:
#         st.info("🔄 Processing your question...") # Show progress indicator
#         try:
#             # Send the question to the FastAPI backend
#             response = requests.post(BACKEND_URL, json={"question": user_question})
#             response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

#             # Get the result from the backend response
#             result_data = response.json()
#             answer = result_data.get("result", "Error: No result field in response.")

#             # Display the result
#             st.success("✅ Processing Complete!")
#             st.markdown("---")
#             st.markdown(answer) # Use markdown to render formatting from the backend

#         except requests.exceptions.RequestException as e:
#             st.error(f"⚠️ Could not connect to the backend: {e}")
#             st.error(f"Please ensure the backend server is running at {BACKEND_URL.replace('/query','')} and accessible.")
#         except Exception as e:
#             st.error(f"An unexpected error occurred: {e}")
#     else:
#         st.warning("Please enter a question before submitting.")

# # --- Optional: Add Instructions or Info ---
# st.sidebar.header("How it Works")
# st.sidebar.markdown("""
# 1.  Enter your question about the data in the text box.
# 2.  Click "Get Answer".
# 3.  The question is sent to a backend service.
# 4.  The backend uses AI and database information (,) to:
#     * Find relevant tables.
#     * Generate a SQL query.
#     * Run the query.
#     * Interpret the results.
# 5.  The final answer is displayed.
# """)
# st.sidebar.header("Project Files")
# st.sidebar.markdown(f"""
# - Backend Logic: `app/main.py`, `app/sql_functions.py`
# - Backend Server: `backend.py`
# - Frontend UI: `frontend.py`
# """) # Add citations here




import streamlit as st
import requests
import os
import re

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/query")

st.set_page_config(page_title="SQL Query Assistant", layout="wide")
st.title("📊 SQL Query Assistant")
st.caption("Ask a question about your data in natural language.")

# Input
user_question = st.text_area("Enter your question here:", height=100)

# Helper to extract and format sections
def format_output(raw_output):
    sections = {
        "Input Question": "",
        "SQL Query": "",
        "SQL Output": "",
        "Answer": ""
    }
    for key in sections.keys():
        pattern = rf"{key}:\s*(.*?)\s*(?=\n[A-Z]|$)"
        match = re.search(pattern, raw_output, re.DOTALL)
        if match:
            sections[key] = match.group(1).strip()
    return sections

# Button
if st.button("Get Answer"):
    if user_question:
        st.info("🔄 Processing your question...")
        try:
            response = requests.post(BACKEND_URL, json={"question": user_question})
            response.raise_for_status()
            result_data = response.json()
            answer = result_data.get("result", "❌ Error: No result field in response.")

            st.success("✅ Processing Complete!")
            st.markdown("---")

            # Format and display clean blocks
            blocks = format_output(answer)

            with st.container():
                st.subheader("📝 Input Question")
                st.code(blocks["Input Question"], language="markdown")

                st.subheader("💡 SQL Query")
                st.code(blocks["SQL Query"], language="sql")

                st.subheader("📄 SQL Output")
                st.code(blocks["SQL Output"], language="text")

                st.subheader("✅ Final Answer")
                st.success(blocks["Answer"])

        except requests.exceptions.RequestException as e:
            st.error(f"⚠️ Could not connect to the backend: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
    else:
        st.warning("Please enter a question before submitting.")

# Sidebar Info
st.sidebar.header("How it Works")
st.sidebar.markdown("""
1. Enter your question in natural language.
2. Click **Get Answer**.
3. The backend:
   - Finds relevant tables.
   - Generates a SQL query.
   - Executes the query.
   - Interprets the results.
4. The answer is returned and displayed clearly.
""")
st.sidebar.header("Project Files")
st.sidebar.markdown("""
- 🧠 Backend Logic: `app/main.py`, `app/sql_functions.py`
- 🔌 Backend Server: `backend.py`
- 🎨 Frontend UI: `frontend.py`
""")
