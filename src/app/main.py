import os
from dotenv import load_dotenv
import time

from langchain import HuggingFaceHub
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings

from langchain.chat_models import ChatOpenAI
from langchain.llms import VertexAI

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from sql_functions import (
    similar_doc_search, identify_schemas, connect_db, prioritize_tables,
    get_table_info, get_sql_dialect, llm_create_sql, llm_check_sql,
    run_sql, llm_debug_error, llm_debug_empty, llm_analyze
)

# Setup embeddings using HuggingFace and the directory location
embeddings = HuggingFaceEmbeddings()
persist_dir = '../data/processed/chromadb'
db_filepath = '../data/raw/spider/database/'

# Load from disk
vectordb = Chroma(persist_directory=persist_dir, embedding_function=embeddings)

# Get API key
load_dotenv()
hf_api_token = os.getenv('hf_token')

# Use OpenAI's GPT model
llm = ChatOpenAI(
    model_name="gpt-3.5-turbo",
    temperature=0.05,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

def sql_copilot(user_question: str, language_model=llm, max_attempts=3):
    print("\nIdentifying most likely schemas...")
    db_documents = similar_doc_search(question=user_question, vector_database=vectordb, top_k=3)

    top_schemas = identify_schemas(db_documents)
    print(top_schemas)
    result = None

    for schema in list(top_schemas):
        print("\nConnecting to " + schema + " schema...")
        db = connect_db(db_path=db_filepath, target_schema=schema)
        print("...Connected to database.")
        print(db.get_usable_table_names())

        tables_sorted = prioritize_tables(documents=db_documents, target_schema=schema, sql_database=db)
        tables_info = get_table_info(tables=tables_sorted, database=db)
        sql_dialect = get_sql_dialect(database=db)

        print("\nCalling to language model...")
        try:
            sql_statement = llm_create_sql(sql_dialect=sql_dialect, table_info=tables_info, question=user_question, lang_model=language_model)
            print("\nTry this SQL statement: " + sql_statement)
        except ValueError as err_msg:
            print("\n" + str(err_msg))
            print('\nMoving on to try the next schema...')
            result = 'FAIL'
            continue

        print("\nValidating SQL...")
        validated_sql = llm_check_sql(sql_query=sql_statement, sql_dialect=sql_dialect, lang_model=language_model)
        print("...SQL validated.")

        attempt = 1
        query_to_run = validated_sql
        print("\nRunning query on database...")
        while attempt <= max_attempts:
            print("Attempting query:", query_to_run)
            query_result = run_sql(database=db, sql_query=query_to_run)

            if query_result[:5] == 'Error':
                if attempt >= max_attempts:
                    result = 'FAIL'
                    output = f"Unable to execute the SQL query after {max_attempts} attempts."
                    break

                print("\nThat query returned an error. Working on debugging...")
                query_to_run = llm_debug_error(sql_query=query_to_run, error_message=query_result, lang_model=language_model)
                attempt += 1
                time.sleep(1)
                print("\nTrying again...")

            elif query_result == '[]':
                if attempt >= max_attempts:
                    result = 'FAIL'
                    output = f"['']\nQuery returned blank results after {max_attempts} attempts."
                    break

                print("\nThat query returned no results. Working on debugging...")
                query_to_run = llm_debug_empty(sql_query=query_to_run, quesiton=user_question, lang_model=language_model)
                attempt += 1
                time.sleep(1)
                print("\nTrying again...")

            else:
                result = 'SUCCESS'
                llm_answer = llm_analyze(query_result=query_result, question=user_question, lang_model=language_model)

                output = f"""
                    Input Question: {user_question}
                    SQL Query: {query_to_run}
                    SQL Output: {query_result}
                    Answer: {llm_answer}"""
                break

        if result == 'SUCCESS':
            break

    if result == 'SUCCESS':
        print("\nHere is what I found:")
        print(output)
        return output
    else:
        print("Sorry, I was not able to find the answer to your question.")
        return "Sorry, I was not able to find the answer to your question."

def main():
    question = input("What would you like to know from your data?: ")
    sql_copilot(user_question=question)

if __name__ == '__main__':
    main()
