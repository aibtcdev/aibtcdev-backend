# streamlit_app.py
import streamlit as st
import requests

# Set up the Streamlit page configuration
st.set_page_config(page_title="Chat with LLM", layout="centered")

# Streamlit UI Elements
st.title("💬 LLM Chat Interface")

# Initialize session state to store chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! How can I help you today?"}
    ]
if "session_id" not in st.session_state:
    st.session_state.session_id = None


# Function to display chat messages
def display_chat():
    for message in st.session_state.messages:
        role = "🤖 Assistant" if message["role"] == "assistant" else "🧑‍💻 You"
        st.markdown(f"**{role}:** {message['content']}")


# User input form
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Enter your message:", key="user_input")
    submitted = st.form_submit_button("Send")

# On form submission, send the user input to the API and update chat history
if submitted and user_input:
    api_url = f"http://localhost:8000/chat?session_id={st.session_state.session_id}"  # Update if your FastAPI backend runs elsewhere
    payload = {"user_message": user_input}

    try:
        response = requests.post(api_url, json=payload)
        response_data = response.json()

        # Update session_id and chat history
        st.session_state.session_id = response_data.get(
            "session_id", st.session_state.session_id
        )
        assistant_response = response_data.get(
            "response", "Oops, something went wrong!"
        )

        # Append messages to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.messages.append(
            {"role": "assistant", "content": assistant_response}
        )

    except requests.exceptions.RequestException as e:
        st.error(f"Error: {e}")

# Display the chat history
display_chat()
