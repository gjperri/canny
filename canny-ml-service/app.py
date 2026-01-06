import psycopg2
import pandas as pd
import os
import json
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.tools import DuckDuckGoSearchRun
from flask import Flask, jsonify
from flask_cors import CORS

# Init app
app = Flask(__name__)
CORS(app)

def get_db_conn():
    conn = psycopg2.connect(
        host="localhost",
        database="canny",
        user="gabrielperri",
        password=""
    )
    return conn

@tool
def get_user_learning_materials(user_id: int) -> str:
    """
    Fetches what learning materials a user is currently reading or has completed.
    Returns a formatted string with the user's learning materials.
    
    Args:
        user_id: The ID of the user to fetch materials for
    """
    try:
        conn = get_db_conn()
        
        query = """
            SELECT 
                li.title,
                li.author,
                li.type,
                li.status
            FROM learning_items li
            WHERE li.is_public = true AND li.user_id = %s
            ORDER BY li.started_at DESC
        """
        
        df = pd.read_sql(query, conn, params=(user_id,))
        conn.close()
        
        if df.empty:
            return f"User {user_id} has no learning materials yet."
        
        # Format as readable string
        materials_list = []
        for _, row in df.iterrows():
            status = "currently learning" if row['status'] == 'currently_learning' else "completed"
            material = f"- {row['title']}"
            if row['author']:
                material += f" by {row['author']}"
            material += f" ({row['type']}, {status})"
            materials_list.append(material)
        
        return f"User {user_id}'s learning materials:\n" + "\n".join(materials_list)
    
    except Exception as e:
        return f"Error fetching materials for user {user_id}: {str(e)}"

@tool
def search_similar_content(query: str) -> str:
    """
    Search the internet for similar books, courses, or learning materials.
    Use this to find recommendations based on topics or titles.
    
    Args:
        query: The search query (e.g., "books similar to Deep Learning by Ian Goodfellow")
    """
    try:
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        return results
    except Exception as e:
        return f"Error searching: {str(e)}"

# Recommendation route for a specific user
@app.route('/api/recommendations/users/<int:user_id>', methods=['GET'])
def recommend_learning_items(user_id):
    try:
        # Initialize Claude with Anthropic API
        # Make sure to set ANTHROPIC_API_KEY in your environment
        model = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.7,
            timeout=30,
            max_tokens=2000
        )
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a helpful literary and personal learning advisor. 

        You have access to these tools:
        1. get_user_learning_materials: Fetches what a user is currently learning
        2. search_similar_content: Searches the internet for similar books, courses, or content

        Your task:
        1. First, get the user's current learning materials
        2. Then search the internet for 2-3 highly relevant recommendations
        3. Return ONLY a JSON array of recommendations in this exact format:
        [
        {{"title": "Book/Course Title", "author": "Author Name", "type": "book/course/article", "reason": "Why this is recommended"}},
        {{"title": "Another Title", "author": "Author Name", "type": "book/course", "reason": "Why this is recommended"}}
        ]

        Be specific and only recommend high-quality, relevant content that truly matches their interests."""),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                    ("user", "{input}")
                ])
        
        # Create tools list
        tools = [get_user_learning_materials, search_similar_content]
        
        # Create agent (graph for some reason?)
        graph = create_agent(
            model=model,
            tools=tools,
            system_prompt="""You are a helpful literary and personal learning advisor. 

        You have access to these tools:
        1. get_user_learning_materials: Fetches what a user is currently learning
        2. search_similar_content: Searches the internet for similar books, courses, or content

        Your task:
        1. First, get the user's current learning materials
        2. Then search the internet for 2-3 highly relevant recommendations
        3. Return ONLY a JSON array of recommendations in this exact format:
        [
        {"title": "Book/Course Title", "author": "Author Name", "type": "book/course/article", "reason": "Why this is recommended"},
        {"title": "Another Title", "author": "Author Name", "type": "book/course", "reason": "Why this is recommended"}
        ]
        
        IMPORTANT: Return ONLY the JSON array with no additional text, no markdown code blocks (no ```json), and no explanations before or after.

        Be specific and only recommend high-quality, relevant content that truly matches their interests."""
        )
        
        user_id = 1
        inputs = {
            "messages": [
                {
                    "role": "user",
                    "content": f"Find and recommend 2-3 learning items for user {user_id} based on their current materials. Search the internet to find the best recommendations."
                }
            ]
        }

        # Format and return chunks
        final_ai_message = None
        final_ai_message = None
        for chunk in graph.stream(inputs, stream_mode="updates"):
            # Each chunk is a dict, look for 'model' -> 'messages'
            if 'model' in chunk and 'messages' in chunk['model']:
                for msg in chunk['model']['messages']:
                    # AIMessage is the final output from the agent
                    if hasattr(msg, 'content'):
                        # If content is a list, get the last text
                        if isinstance(msg.content, list):
                            for part in msg.content:
                                if isinstance(part, dict) and part.get('type') == 'text':
                                    final_ai_message = part['text']
                        elif isinstance(msg.content, str):
                            final_ai_message = msg.content

        if final_ai_message:
            # Try to parse as JSON array, else return as text
            try:
                recommendations = json.loads(final_ai_message)
                return jsonify({"recommendations": recommendations})
            except Exception:
                # Not valid JSON, return as plain text
                return jsonify({"recommendations": [], "raw": final_ai_message})

        return jsonify({"recommendations": [], "error": "No recommendations found."}), 500
    
    except Exception as e:
        print(f"Error in recommendation endpoint: {str(e)}")
        return jsonify({"error": str(e), "recommendations": []}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)