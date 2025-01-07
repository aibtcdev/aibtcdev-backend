I'll create a structured plan for testing each API endpoint module. Based on the existing run_tests.sh and utils.sh setup, here's a modular testing approach:                                                        

 1 File Structure Create a test file for each API module following this pattern:                                                                                                                                     

                                                                                                                                                                                                                     
 tests/                                                                                                                                                                                                              
 ├── run_tests.sh      (existing)                                                                                                                                                                                    
 ├── utils.sh          (existing)                                                                                                                                                                                    
 ├── test_chat.sh      (new)                                                                                                                                                                                         
 ├── test_crew.sh      (new)                                                                                                                                                                                         
 ├── test_metrics.sh   (new)                                                                                                                                                                                         
 ├── test_public_crews.sh (new)                                                                                                                                                                                      
 └── test_public_stats.sh (new)                                                                                                                                                                                      
                                                                                                                                                                                                                     

 2 Standard Test File Template Each test file should follow this structure:                                                                                                                                          

                                                                                                                                                                                                                     
 #!/bin/bash                                                                                                                                                                                                         
                                                                                                                                                                                                                     
 # Source utils                                                                                                                                                                                                      
 source "$(dirname "$0")/utils.sh"                                                                                                                                                                                   
                                                                                                                                                                                                                     
 test_<module_name>() {                                                                                                                                                                                              
     echo "Testing <module_name> endpoints..."                                                                                                                                                                       
                                                                                                                                                                                                                     
     # Basic endpoint tests                                                                                                                                                                                          
     test_endpoint "</path>" 200 "<description>"                                                                                                                                                                     
                                                                                                                                                                                                                     
     # CORS tests                                                                                                                                                                                                    
     test_cors "</path>" "<description>"                                                                                                                                                                             
                                                                                                                                                                                                                     
     # Additional specific tests...                                                                                                                                                                                  
 }                                                                                                                                                                                                                   
                                                                                                                                                                                                                     

 3 Instructions Per Module                                                                                                                                                                                           

For each API module, here are the specific instructions:                                                                                                                                                             

test_public_stats.sh:                                                                                                                                                                                                

                                                                                                                                                                                                                     
 1. Create test for GET /public_stats/                                                                                                                                                                               
    - Test successful response (200)                                                                                                                                                                                 
    - Verify response structure matches StatsResponse model                                                                                                                                                          
    - Test CORS headers                                                                                                                                                                                              
 2. Add error condition tests                                                                                                                                                                                        
    - Test external API timeout                                                                                                                                                                                      
    - Test malformed response handling                                                                                                                                                                               
                                                                                                                                                                                                                     

test_public_crews.sh:                                                                                                                                                                                                

                                                                                                                                                                                                                     
 1. Create test for GET /public-crews                                                                                                                                                                                
    - Test successful response (200)                                                                                                                                                                                 
    - Verify response contains array of Crew objects                                                                                                                                                                 
    - Verify email masking                                                                                                                                                                                           
    - Test CORS headers                                                                                                                                                                                              
 2. Add empty result test                                                                                                                                                                                            
 3. Test crew object structure validation                                                                                                                                                                            
                                                                                                                                                                                                                     

test_metrics.sh:                                                                                                                                                                                                     

                                                                                                                                                                                                                     
 1. Create test for GET /crews_metrics                                                                                                                                                                               
    - Test successful response (200)                                                                                                                                                                                 
    - Verify CrewsByDateResponse structure                                                                                                                                                                           
    - Test CORS headers                                                                                                                                                                                              
 2. Test empty metrics response                                                                                                                                                                                      
 3. Verify date formatting in response                                                                                                                                                                               
                                                                                                                                                                                                                     

test_chat.sh:                                                                                                                                                                                                        

                                                                                                                                                                                                                     
 1. Create tests for all endpoints:                                                                                                                                                                                  
    - POST / (chat trigger)                                                                                                                                                                                          
    - GET /{job_id}/stream                                                                                                                                                                                           
    - POST /threads                                                                                                                                                                                            
    - GET /threads                                                                                                                                                                                             
    - GET /threads/latest                                                                                                                                                                                      
    - GET /threads/{thread_id}                                                                                                                                                                           
    - DELETE /threads/{thread_id}                                                                                                                                                                        
 2. Test authentication requirements                                                                                                                                                                                 
 3. Test SSE streaming functionality                                                                                                                                                                                 
 4. Test thread management                                                                                                                                                                                     
                                                                                                                                                                                                                     

test_crew.sh:                                                                                                                                                                                                        

                                                                                                                                                                                                                     
 1. Create tests for all endpoints:                                                                                                                                                                                  
    - GET /public                                                                                                                                                                                                    
    - GET /tools                                                                                                                                                                                                     
    - POST /{crew_id}                                                                                                                                                                                                
    - GET /jobs                                                                                                                                                                                                      
    - GET /jobs/{job_id}/stream                                                                                                                                                                                      
    - DELETE /jobs/{job_id}/cancel                                                                                                                                                                                   
 2. Test authentication requirements                                                                                                                                                                                 
 3. Test job management functionality                                                                                                                                                                                
 4. Test SSE streaming                                                                                                                                                                                               
                                                                                                                                                                                                                     

 4 Integration Steps                                                                                                                                                                                                 
 5 Add each new test file to run_tests.sh:                                                                                                                                                                           

                                                                                                                                                                                                                     
 source "$SCRIPT_DIR/test_public_stats.sh"                                                                                                                                                                           
 source "$SCRIPT_DIR/test_public_crews.sh"                                                                                                                                                                           
 source "$SCRIPT_DIR/test_metrics.sh"                                                                                                                                                                                
 source "$SCRIPT_DIR/test_chat.sh"                                                                                                                                                                                   
 source "$SCRIPT_DIR/test_crew.sh"                                                                                                                                                                                   
                                                                                                                                                                                                                     

 2 Add test execution calls in the main section:                                                                                                                                                                     

                                                                                                                                                                                                                     
 # Run all test suites                                                                                                                                                                                               
 test_public_stats                                                                                                                                                                                                   
 test_public_crews                                                                                                                                                                                                   
 test_metrics                                                                                                                                                                                                        
 test_chat                                                                                                                                                                                                           
 test_crew                                                                                                                                                                                                           
                                                                                                                                                                                                                     

 5 Common Requirements for All Test Files:                                                                                                                                                                           

                                                                                                                                                                                                                     
 1. Use the provided test_endpoint() function from utils.sh                                                                                                                                                          
 2. Use the provided test_cors() function from utils.sh                                                                                                                                                              
 3. Follow the global counter pattern using $TOTAL_TESTS and $FAILED_TESTS                                                                                                                                           
 4. Use consistent error messaging format                                                                                                                                                                            
 5. Include both positive and negative test cases                                                                                                                                                                    
 6. Test authentication where required                                                                                                                                                                               
 7. Verify response structure matches API models                                                                                                                                                                     
 8. Use the shared TEST_ADDRESSES array where needed                                                                                                                                                                 
                                                                                                                                                                                                                     

This plan ensures consistent test coverage across all API modules while maintaining modularity and reusability. Each developer can work independently on their assigned module while following the same patterns and 
standards.       
