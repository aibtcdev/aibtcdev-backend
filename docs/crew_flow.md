 # Crew Execution Flow                                                                                                
                                                                                                                      
 ```mermaid                                                                                                           
 sequenceDiagram                                                                                                      
     participant Client                                                                                               
     participant FastAPI                                                                                              
     participant CrewRouter                                                                                           
     participant CrewServices                                                                                         
     participant AIBTC_Crew                                                                                           
     participant Agents                                                                                               
     participant Tools                                                                                                
                                                                                                                      
     Client->>FastAPI: POST /crew/execute_crew/{crew_id}                                                              
     FastAPI->>CrewRouter: execute_crew_endpoint(crew_id, input_str)                                                  
     CrewRouter->>CrewServices: execute_crew(crew_id, input_str)                                                      
                                                                                                                      
     CrewServices->>AIBTC_Crew: Initialize Crew                                                                       
     AIBTC_Crew->>AIBTC_Crew: setup_agents()                                                                          
     AIBTC_Crew->>AIBTC_Crew: setup_tasks(input_str)                                                                  
                                                                                                                      
     loop For each task                                                                                               
         AIBTC_Crew->>Agents: Execute task                                                                            
         Agents->>Tools: Use required tools                                                                           
         Tools-->>Agents: Return tool results                                                                         
         Agents-->>AIBTC_Crew: Return task results                                                                    
     end                                                                                                              
                                                                                                                      
     AIBTC_Crew-->>CrewServices: Return final results                                                                 
     CrewServices-->>CrewRouter: Return execution results                                                             
     CrewRouter-->>FastAPI: Return HTTP response                                                                      
     FastAPI-->>Client: Return JSON response 
