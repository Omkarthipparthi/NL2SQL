#Create python functions that interact with db and have multiple entry points to LLMs

import os
import re

from langchain import SQLDatabase
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

### Setup functions to interact with database and llms


def similar_doc_search(question, vector_database, top_k=3):
    """
    Run similarity search through a vectordb query on the user input question and return the k most similar schema-table combinations in document form..
    """
    similar_docs = vector_database.similarity_search(question, k=top_k)

    return similar_docs

def identify_schemas(documents):
    """
    Take in a list of documents created from our similar_doc_search function.
    Use the metadata.
    And convert this into a set of unique schemas returned by that search.
    """
    target_schemas = list(dict.fromkeys([doc.metadata['schema'] for doc in documents]))

    return target_schemas

def connect_db(db_path, target_schema):
    """
    Take in the identified schema and connect to the sqlite database with that name
    """
    db_filepath = db_path + target_schema + '/'
    db_filename = target_schema + '.sqlite'

    #point to database
    base_dir = os.path.dirname(os.path.abspath(db_filepath+db_filename)) #get the full path within the device
    db_path = os.path.join(base_dir, db_filename) #combine with filename to get db_path
    db = SQLDatabase.from_uri("sqlite:///" + db_path) #connect via the lanchain method

    return db

def prioritize_tables(documents, target_schema, sql_database):
    """
    Take in a list of similar_doc_search documents and prioritize tables from the same schema.
    Sort all tables in the database based on the priority list.
    """
    table_sorting = set(doc.metadata['table'] for doc in documents if doc.metadata['schema'] == target_schema)
    table_names = sql_database.get_usable_table_names()
    table_indices = {table: index for index, table in enumerate(table_sorting)}

    priority_tables = sorted(table_names, key=lambda x: (table_indices.get(x, float('inf')), table_names.index(x)))

    return priority_tables

def get_table_info(tables, database):
    """
    Initialize an empty list, then loop through the list of tables in the database and save the DDL and 3 sample rows for each to a variable.
    """
    table_info = []
    for table in tables:
        table_name = table
        info = database.get_table_info(table_names=[table])
        table_info.append('DDL for the ' + table_name + ' table:' + info)

    #merge the items
    tables_summary = '\n\n'.join(table_info)

    return tables_summary

def get_sql_dialect(database):
    """
    Return the sql dialaect from the database.
    """
    sql_dialect = database.dialect

    return sql_dialect

def llm_create_sql(sql_dialect, table_info, question, lang_model):
    create_prompt = PromptTemplate(
    input_variables=[],
    # template = f"""
    #     You are a SQL Query Writer. Given an input question, first create a working {sql_dialect} SQL statement to find the answer to an input question and then return only the syntactically correct SQL statement.
        
    #     Use one or multiple of these tables:
    #     {table_info} 

    #     Input question: "{question}"
    # """ )

    # template = f"""
    #     You are a SQL Query Writer. Given an input question and the following schema info, write a working {sql_dialect} SQL query to answer it.

    #     Respond with only the SQL query. Prefer simple logic and avoid unnecessary joins if data is available directly.

    #     {table_info}

    #     Input question: "{question}"
    #  """
    # )

    # template = f"""
    #     You are a SQL expert. Given the database schema details below and a user question, write a syntactically correct {sql_dialect} SQL query that answers the question.

    #     Only respond with the SQL query. Avoid unnecessary joins or complex logic unless required. Use the most relevant table(s) based on names and column fields.

    #     - Use `JOIN` only if needed (e.g., to get manager/employee relationships).
    #     - For age calculations, assume current date is today's date if birthdate is given.
    #     - If `age` or `Bdate` is present, prefer using that to compute age directly.
    #     - If the user asks about "heads of departments", interpret it as managers or department heads.

    #     Available Tables and Columns:
    #     {table_info}

    #     User Question: "{question}"
    #     """)

    template = f"""
        You are a highly skilled SQL query generator.

        Given:
        - The user's natural language question.
        - A list of database tables and their schema (column names and data types).
        - The target SQL dialect: {sql_dialect}

        Your task:
        - Write a syntactically and logically correct SQL query to answer the question.
        - Use JOINs only when necessary.
        - Use correct date and numeric operations for conditions like age, salary, etc.
        - Avoid hallucinating columns or tables. Only use what is in the provided schema.

        Respond with only the SQL query. Do not include any explanations or extra output.

        Schema:
        {table_info}

        User Question: "{question}"
        """)



    # print("OMKAR",lang_model)

    create_chain = LLMChain(llm=lang_model, prompt=create_prompt, verbose=False)

    sql_query = create_chain.predict()
    # sql_query.trim('''')
    print("\nSQL statement created: " + sql_query)
    # sql_query = "SELECT COUNT(*) FROM head WHERE age > 56;"
    return sql_query

def llm_check_sql(sql_query, sql_dialect, lang_model):
    validate_prompt = PromptTemplate(
    input_variables=[],
    template = f"""{sql_query}

        Double check the {sql_dialect} query above for common mistakes, including:
        - Using NOT IN with NULL values
        - Using UNION when UNION ALL should have been used
        - Using BETWEEN for exclusive ranges
        - Data type mismatch in predicates
        - Properly quoting identifiers
        - Using the correct number of arguments for functions
        - Casting to the correct data type
        - Using the proper columns for joins

        If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query."""
    )

    validate_chain = LLMChain(llm=lang_model, prompt=validate_prompt, verbose=False)

    checked_sql = validate_chain.predict()

    # return checked_sql
    return extract_sql(checked_sql)


def extract_sql(text: str) -> str:
    """
    Extracts the SQL query from a mixed LLM response.
    Assumes the SQL is between triple backticks or starts with SELECT/UPDATE/INSERT/DELETE.
    Also trims any trailing commentary or repeated text.
    """
    match = re.search(r"```(?:sql)?\s*(.+?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"(SELECT|INSERT|UPDATE|DELETE)\s.+", text, re.IGNORECASE | re.DOTALL)
    if match:
        sql_start = text.lower().find(match.group(1).lower())
        sql_text = text[sql_start:]
        sql_lines = sql_text.strip().splitlines()
        for i, line in enumerate(sql_lines):
            if not line.strip().endswith(";"):
                continue
            sql_lines = sql_lines[:i+1]
            break
        return " ".join(sql_lines).strip()

    return text.strip()

def run_sql(database, sql_query):
    # sql_query="SELECT COUNT(*) FROM head WHERE age > 56;"
    print("OMKAR2", sql_query)
    query_result = database.run_no_throw(sql_query)

    return query_result

def llm_debug_error(sql_query, error_message, lang_model):
    """
    To be executed if the SQL query returns an error message
    Will provide the error message to the LLM and ask it to debug, returning a new query
    """
    #setup the debugging prompt
    debug_error_prompt = PromptTemplate(
        input_variables=[],
        template = f"""{sql_query}

    The query above produced the following error:

    {error_message}

    Rewrite the query with the error fixed:"""
    )

    debug_error_chain = LLMChain(llm=lang_model, prompt=debug_error_prompt, verbose=False)

    debugged_query = debug_error_chain.predict()

    return debugged_query

def llm_debug_empty(sql_query, question, lang_model):
    """
    To be executed if the SQL query returns an empty string.
    Will provide a prompt to the LLM asking it to re-review the original question and data and write a new query
    """
    debug_empty_prompt = PromptTemplate(
        input_variables=[],
        template = f"""{sql_query}

        The query above produced no result. Try rewriting the query so it will return results to this question "{question}":"""
        )
    
    debug_empty_chain = LLMChain(llm=lang_model, prompt=debug_empty_prompt, verbose=False)

    debugged_query = debug_empty_chain.predict()

    return debugged_query

def llm_analyze(query_result, question, lang_model):
    """
    To be executed if the run SQL query returns a valid results.
    Will provide the full output of the original question, final sql query, and answer.
    """
    analyze_prompt = PromptTemplate(
        input_variables=[],
        template = f"""
    You are an expert data analyst. Given an output of an SQL query, first look at the output and then determine the answer to a user question.
    
    SQL Output: "{query_result}"
    Question: "{question}"

    Describe your answer in one sentence:
    """
        )
    
    analyze_chain = LLMChain(llm=lang_model, prompt=analyze_prompt, verbose=False)
    
    llm_answer = analyze_chain.predict()

    return llm_answer