# Swagger/OpenAPI Documentation Usage Guide

This guide explains how to use the comprehensive Swagger/OpenAPI documentation system implemented for the AI BTC Dev Backend API.

## Quick Start

### 1. Access Live Documentation

When the API server is running, you can access interactive documentation at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
- **Export Endpoint**: [http://localhost:8000/openapi/export](http://localhost:8000/openapi/export)

### 2. Generate Offline Documentation

Use the documentation generator script to create offline documentation in multiple formats:

```bash
# Generate all formats
python scripts/generate_docs.py

# Generate specific format only
python scripts/generate_docs.py --format json
python scripts/generate_docs.py --format yaml
python scripts/generate_docs.py --format html
python scripts/generate_docs.py --format redoc
python scripts/generate_docs.py --format postman

# Specify output directory
python scripts/generate_docs.py --output-dir my-docs/

# Check if API is running before generation
python scripts/generate_docs.py --check-api
```

## Documentation Features

### 📚 Comprehensive API Documentation

The system automatically generates documentation for:

- **All API endpoints** with detailed descriptions
- **Request/response schemas** with examples
- **Authentication methods** (Bearer tokens, API keys)
- **Error responses** with status codes and examples
- **Interactive testing** directly in the browser

### 🔒 Security Documentation

- **Authentication schemes** clearly documented
- **Security requirements** for each endpoint
- **Example requests** with proper authentication headers
- **Webhook authentication** for external integrations

### 📋 Multiple Export Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| **JSON** | OpenAPI 3.1.0 JSON schema | API tools, validation |
| **YAML** | OpenAPI 3.1.0 YAML schema | Documentation as code |
| **HTML** | Standalone Swagger UI | Offline browsing |
| **ReDoc** | Alternative documentation viewer | Clean, readable docs |
| **Postman** | Postman collection | API testing and automation |

## Using the Documentation

### 1. Interactive Testing with Swagger UI

1. **Access Swagger UI**: Go to [http://localhost:8000/docs](http://localhost:8000/docs)
2. **Authenticate**: Click "Authorize" button and enter your token
3. **Test Endpoints**: Expand any endpoint and click "Try it out"
4. **Execute Requests**: Fill in parameters and click "Execute"
5. **View Responses**: See real API responses with status codes

### 2. Authentication Setup

The API supports two authentication methods:

#### Bearer Token Authentication
```bash
# In Swagger UI, use the "Authorize" button with:
Bearer your_session_token_here
```

#### API Key Authentication
```bash
# Add to request headers:
X-API-Key: your_api_key_here
```

### 3. Example API Calls

All endpoints are documented with examples. Here are some key patterns:

#### Get Available Tools
```bash
curl -H "Authorization: Bearer your_token" \
  http://localhost:8000/tools/
```

#### Execute Faktory Buy Order
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{"btc_amount": "0.0004", "dao_token_dex_contract_address": "SP..."}' \
  http://localhost:8000/tools/faktory/execute_buy
```

#### Create DAO Proposal
```bash
curl -X POST -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_account_contract": "SP...",
    "action_proposals_voting_extension": "SP...",
    "action_proposal_contract_to_execute": "SP...",
    "dao_token_contract_address": "SP...",
    "message": "Proposal to improve DAO governance"
  }' \
  http://localhost:8000/tools/dao/action_proposals/propose_send_message
```

## Advanced Usage

### 1. Postman Integration

1. **Generate Postman Collection**:
   ```bash
   python scripts/generate_docs.py --format postman
   ```

2. **Import to Postman**:
   - Open Postman
   - Click "Import"
   - Select `docs/generated/postman_collection.json`
   - Collection includes pre-configured authentication

3. **Set Environment Variables**:
   - `baseUrl`: `http://localhost:8000`
   - `BEARER_TOKEN`: Your authentication token

### 2. API Client Generation

Use the OpenAPI schema to generate client libraries:

```bash
# Using OpenAPI Generator
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g python \
  -o ./python-client

# Using Swagger Codegen
swagger-codegen generate \
  -i http://localhost:8000/openapi.json \
  -l typescript-fetch \
  -o ./typescript-client
```

### 3. Documentation in CI/CD

Add documentation generation to your CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Generate API Documentation
  run: |
    python scripts/generate_docs.py --format all
    
- name: Deploy Documentation
  uses: peaceiris/actions-gh-pages@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./docs/generated
```

## Customization

### 1. Adding Endpoint Documentation

Enhance your API endpoints with comprehensive documentation:

```python
@router.post(
    "/your-endpoint",
    summary="Short Description",
    description="Detailed description with **markdown** support",
    responses={
        200: {
            "description": "Success response",
            "content": {
                "application/json": {
                    "example": {"result": "success"}
                }
            }
        },
        400: {
            "description": "Bad request",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid parameters"}
                }
            }
        }
    },
    tags=["your-category"]
)
async def your_endpoint():
    """
    Detailed endpoint documentation.
    
    This supports **markdown** formatting:
    - Lists
    - **Bold text**
    - `code snippets`
    
    **Authentication Required:** Yes
    """
    pass
```

### 2. Custom Response Models

Create Pydantic models for better documentation:

```python
from pydantic import BaseModel, Field

class YourResponse(BaseModel):
    """Response model for your endpoint."""
    
    success: bool = Field(..., description="Operation success status")
    data: dict = Field(..., description="Response data")
    message: str = Field(..., description="Human-readable message")

@router.post("/your-endpoint", response_model=YourResponse)
async def your_endpoint():
    pass
```

### 3. Adding Examples

Include request/response examples:

```python
@router.post(
    "/your-endpoint",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "examples": {
                        "success_example": {
                            "summary": "Successful operation",
                            "value": {
                                "success": True,
                                "data": {"id": "123"},
                                "message": "Operation completed"
                            }
                        }
                    }
                }
            }
        }
    }
)
```

## Troubleshooting

### Common Issues

1. **Documentation not updating**: Restart the server after code changes
2. **Authentication not working**: Check token format and permissions
3. **Examples not showing**: Verify Pydantic model examples are properly defined
4. **Generation script failing**: Ensure all dependencies are installed (`pip install -e .[docs]`)

### Getting Help

- **Check Logs**: Server logs show documentation generation issues
- **Validate Schema**: Use online OpenAPI validators
- **Test Locally**: Always test documentation with a running server
- **Report Issues**: Create GitHub issues for documentation bugs

## Best Practices

### 1. Documentation Standards

- **Use clear summaries**: Keep endpoint summaries under 50 characters
- **Provide detailed descriptions**: Explain what the endpoint does and when to use it
- **Include examples**: Always provide request/response examples
- **Document error cases**: Include all possible error responses
- **Tag consistently**: Use consistent tags for endpoint grouping

### 2. Maintenance

- **Regular updates**: Update documentation when API changes
- **Review accuracy**: Periodically verify examples work correctly
- **Test generation**: Run documentation generation in CI/CD
- **Monitor feedback**: Track documentation usage and feedback

### 3. Security

- **Sanitize examples**: Ensure examples don't contain real credentials
- **Document auth requirements**: Clearly mark which endpoints require authentication
- **Explain permissions**: Document what permissions are needed for each endpoint

---

## Links

- **Live Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Live ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Specification**: [https://swagger.io/specification/](https://swagger.io/specification/)
- **FastAPI Documentation**: [https://fastapi.tiangolo.com/tutorial/metadata/](https://fastapi.tiangolo.com/tutorial/metadata/)
- **Swagger UI Documentation**: [https://swagger.io/tools/swagger-ui/](https://swagger.io/tools/swagger-ui/) 