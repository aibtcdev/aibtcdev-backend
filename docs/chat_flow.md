# Chat Endpoint Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant ChatRouter
    participant SessionManager
    participant CrewManager
    participant UserChatSpecialistCrew
    participant Agents
    participant Tools

    Client->>FastAPI: POST /chat
    FastAPI->>ChatRouter: chat_endpoint(request)
    ChatRouter->>SessionManager: get_or_create_session()
    SessionManager-->>ChatRouter: session_id
    
    ChatRouter->>SessionManager: Get session messages
    SessionManager-->>ChatRouter: messages

    ChatRouter->>SessionManager: Add user message
    ChatRouter->>SessionManager: trim_messages()
    
    ChatRouter->>CrewManager: kickoff_thread(messages, session_id)
    
    CrewManager->>UserChatSpecialistCrew: Initialize Crew
    UserChatSpecialistCrew->>UserChatSpecialistCrew: setup_agents()
    UserChatSpecialistCrew->>UserChatSpecialistCrew: setup_tasks(user_input)
    
    loop For each task
        UserChatSpecialistCrew->>Agents: Execute task
        
        alt User asks question
            Agents->>Agents: Process question
        else User requests task
            Agents->>Tools: Execute appropriate tool
            Tools-->>Agents: Return tool results
        end
        
        Agents-->>UserChatSpecialistCrew: Return response
    end

    UserChatSpecialistCrew-->>CrewManager: Return final response
    CrewManager-->>ChatRouter: Return thread response
    ChatRouter-->>FastAPI: Return response object
    FastAPI-->>Client: Return JSON response

```

This diagram illustrates the chat endpoint flow, highlighting:
1. Session management
2. Message handling
3. Crew initialization and execution
4. Task processing logic for questions vs tasks
5. Response flow back to client
