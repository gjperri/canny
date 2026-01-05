from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langchain.chat_models import init_chat_model

# Init app
app = Flask(__name__)
CORS(app)

def get_db_conn():
    conn = psycopg2.connect(
        host="localhost",
        database ="canny",
        user="gabrielperri",
        password=""
    )
    return conn

@tool
def get_user_learning_materials(user_id):
    try:
        # Get the db connection to fetch what the user has learned about
        conn = get_db_conn()

        # Get the learning items
        query = """
            SELECT 
                li.id,
                li.user_id,
                li.title,
                li.author,
                li.type,
                u.full_name
            FROM learning_items li
            JOIN users u ON li.user_id = u.id
            WHERE li.is_public = true AND li.user_id = %s
        """

        # make a dataframe for analysis
        df = pd.read_sql(query, conn, params=(user_id))
        if df.empty:
            return jsonify({'recommendations': []})
        return df
    except Exception as e:
        print("Error connecting")


# Recommendation route for a specific user
@app.route('/api/recommendations/users/<int:user_id>', methods=['GET'])
def recommend_learning_items(user_id):
    model = init_chat_model(
        "claude-sonnet-4-5-20250929",
        temperature=0.5,
        timeout=10,
        max_tokens=1000
    )
    
    SYSTEM_PROMPT = """
    You are a helpful literary and personal learning advisor. You have access to one tool,
     - get_user_learning_materials(user_id)
     Which allows you to get a python dataframe of current reading or media materials the user is learning about. Recommend two books or video 
     media content that is similar to their learning materials or is in the same topic.
    """

    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[get_user_learning_materials],
    )

    config = {"configurable": {"thread_id": "1"}}

    response = agent.invoke(
        {"messages": [{"role": "user", "content": "what is the weather outside?"}]},
        config=config,
        context=Context(user_id="1")
    )