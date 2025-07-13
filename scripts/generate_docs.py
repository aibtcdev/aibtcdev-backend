#!/usr/bin/env python3
"""
Swagger/OpenAPI Documentation Generator

This script generates and exports OpenAPI documentation in multiple formats
for the AI BTC Dev Backend API.
"""

import json
import sys
import yaml
from pathlib import Path
from typing import Dict, Any

import httpx
import asyncio
from app.main import app
from app.lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)


class DocumentationGenerator:
    """Generate and export API documentation in multiple formats."""

    def __init__(self, output_dir: str = "docs/generated"):
        """Initialize the documentation generator.

        Args:
            output_dir: Directory to save generated documentation
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_openapi_schema(self) -> Dict[str, Any]:
        """Get the OpenAPI schema from the FastAPI app.

        Returns:
            The OpenAPI schema as a dictionary
        """
        try:
            schema = app.openapi()
            logger.info("Successfully generated OpenAPI schema")
            return schema
        except Exception as e:
            logger.error(f"Failed to generate OpenAPI schema: {e}")
            raise

    def save_json_schema(self, schema: Dict[str, Any]) -> Path:
        """Save OpenAPI schema as JSON.

        Args:
            schema: The OpenAPI schema dictionary

        Returns:
            Path to the saved JSON file
        """
        json_path = self.output_dir / "openapi.json"

        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved OpenAPI JSON schema to: {json_path}")
            return json_path
        except Exception as e:
            logger.error(f"Failed to save JSON schema: {e}")
            raise

    def save_yaml_schema(self, schema: Dict[str, Any]) -> Path:
        """Save OpenAPI schema as YAML.

        Args:
            schema: The OpenAPI schema dictionary

        Returns:
            Path to the saved YAML file
        """
        yaml_path = self.output_dir / "openapi.yaml"

        try:
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(schema, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"Saved OpenAPI YAML schema to: {yaml_path}")
            return yaml_path
        except Exception as e:
            logger.error(f"Failed to save YAML schema: {e}")
            raise

    def generate_html_docs(self, schema: Dict[str, Any]) -> Path:
        """Generate standalone HTML documentation.

        Args:
            schema: The OpenAPI schema dictionary

        Returns:
            Path to the generated HTML file
        """
        html_path = self.output_dir / "api-docs.html"

        # Escape the schema for embedding in HTML
        schema_json = json.dumps(schema, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{schema.get("info", {}).get("title", "API Documentation")}</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css" />
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        *, *:before, *:after {{
            box-sizing: inherit;
        }}
        body {{
            margin:0;
            background: #fafafa;
        }}
        .swagger-ui .topbar {{
            background-color: #1f2937;
        }}
        .swagger-ui .topbar .download-url-wrapper .select-label {{
            color: #ffffff;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js"></script>
    
    <script>
        window.onload = function() {{
            const ui = SwaggerUIBundle({{
                spec: {schema_json},
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                docExpansion: "list",
                operationsSorter: "method",
                filter: true,
                showExtensions: true,
                showCommonExtensions: true,
                displayRequestDuration: true
            }});
        }};
    </script>
</body>
</html>"""

        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            logger.info(f"Generated standalone HTML documentation: {html_path}")
            return html_path
        except Exception as e:
            logger.error(f"Failed to generate HTML documentation: {e}")
            raise

    def generate_redoc_html(self, schema: Dict[str, Any]) -> Path:
        """Generate ReDoc HTML documentation.

        Args:
            schema: The OpenAPI schema dictionary

        Returns:
            Path to the generated ReDoc HTML file
        """
        redoc_path = self.output_dir / "redoc.html"

        # Escape the schema for embedding in HTML
        schema_json = json.dumps(schema, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{schema.get("info", {}).get("title", "API Documentation")} - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <redoc spec-url="data:application/json;base64,{json.dumps(schema).encode().hex()}"></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
    <script>
        Redoc.init({schema_json}, {{
            scrollYOffset: 50,
            theme: {{
                colors: {{
                    primary: {{
                        main: '#1f2937'
                    }}
                }},
                typography: {{
                    fontSize: '14px',
                    headings: {{
                        fontFamily: 'Montserrat, sans-serif'
                    }}
                }}
            }}
        }}, document.body);
    </script>
</body>
</html>"""

        try:
            with open(redoc_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            logger.info(f"Generated ReDoc HTML documentation: {redoc_path}")
            return redoc_path
        except Exception as e:
            logger.error(f"Failed to generate ReDoc documentation: {e}")
            raise

    def generate_postman_collection(self, schema: Dict[str, Any]) -> Path:
        """Generate Postman collection from OpenAPI schema.

        Args:
            schema: The OpenAPI schema dictionary

        Returns:
            Path to the generated Postman collection file
        """
        postman_path = self.output_dir / "postman_collection.json"

        # Basic Postman collection structure
        collection = {
            "info": {
                "name": schema.get("info", {}).get("title", "API Collection"),
                "description": schema.get("info", {}).get("description", ""),
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {"key": "token", "value": "{{BEARER_TOKEN}}", "type": "string"}
                ],
            },
            "variable": [
                {"key": "baseUrl", "value": "http://localhost:8000", "type": "string"},
                {
                    "key": "BEARER_TOKEN",
                    "value": "your_bearer_token_here",
                    "type": "string",
                },
            ],
            "item": [],
        }

        # Convert OpenAPI paths to Postman requests
        paths = schema.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    request_item = {
                        "name": details.get("summary", f"{method.upper()} {path}"),
                        "request": {
                            "method": method.upper(),
                            "header": [
                                {
                                    "key": "Content-Type",
                                    "value": "application/json",
                                    "type": "text",
                                }
                            ],
                            "url": {
                                "raw": "{{baseUrl}}" + path,
                                "host": ["{{baseUrl}}"],
                                "path": path.strip("/").split("/")
                                if path != "/"
                                else [],
                            },
                            "description": details.get("description", ""),
                        },
                    }

                    # Add request body if present
                    if "requestBody" in details:
                        content = details["requestBody"].get("content", {})
                        if "application/json" in content:
                            schema_ref = content["application/json"].get("schema", {})
                            if "example" in schema_ref:
                                request_item["request"]["body"] = {
                                    "mode": "raw",
                                    "raw": json.dumps(schema_ref["example"], indent=2),
                                }

                    collection["item"].append(request_item)

        try:
            with open(postman_path, "w", encoding="utf-8") as f:
                json.dump(collection, f, indent=2, ensure_ascii=False)

            logger.info(f"Generated Postman collection: {postman_path}")
            return postman_path
        except Exception as e:
            logger.error(f"Failed to generate Postman collection: {e}")
            raise

    def generate_all_formats(self) -> Dict[str, Path]:
        """Generate documentation in all supported formats.

        Returns:
            Dictionary mapping format names to file paths
        """
        logger.info("Starting documentation generation...")

        # Get the OpenAPI schema
        schema = self.get_openapi_schema()

        # Generate all formats
        generated_files = {}

        try:
            generated_files["json"] = self.save_json_schema(schema)
            generated_files["yaml"] = self.save_yaml_schema(schema)
            generated_files["html"] = self.generate_html_docs(schema)
            generated_files["redoc"] = self.generate_redoc_html(schema)
            generated_files["postman"] = self.generate_postman_collection(schema)

            logger.info("Successfully generated all documentation formats")
            return generated_files

        except Exception as e:
            logger.error(f"Failed to generate documentation: {e}")
            raise


def print_summary(generated_files: Dict[str, Path]):
    """Print a summary of generated documentation files.

    Args:
        generated_files: Dictionary of format names to file paths
    """
    print("\n" + "=" * 60)
    print("📚 API Documentation Generated Successfully!")
    print("=" * 60)

    for format_name, file_path in generated_files.items():
        file_size = file_path.stat().st_size
        print(f"📄 {format_name.upper():10} | {file_path} ({file_size:,} bytes)")

    print("\n🔗 Usage Instructions:")
    print("─" * 40)
    print("• JSON/YAML: Import into API tools (Insomnia, Bruno, etc.)")
    print("• HTML: Open in browser for interactive documentation")
    print("• ReDoc: Alternative documentation viewer")
    print("• Postman: Import collection for API testing")

    print("\n🌐 Live Documentation (when server is running):")
    print("─" * 50)
    print("• Swagger UI: http://localhost:8000/docs")
    print("• ReDoc:      http://localhost:8000/redoc")
    print("• OpenAPI:    http://localhost:8000/openapi.json")
    print("• Export:     http://localhost:8000/openapi/export")


async def validate_running_api():
    """Validate that the API is accessible and running.

    Returns:
        bool: True if API is running, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/")
            return response.status_code == 200
    except Exception:
        return False


def main():
    """Main function to generate API documentation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate API documentation in multiple formats"
    )
    parser.add_argument(
        "--output-dir",
        default="docs/generated",
        help="Directory to save generated documentation (default: docs/generated)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "yaml", "html", "redoc", "postman", "all"],
        default="all",
        help="Documentation format to generate (default: all)",
    )
    parser.add_argument(
        "--check-api",
        action="store_true",
        help="Check if API is running before generating docs",
    )

    args = parser.parse_args()

    # Check if API is running (optional)
    if args.check_api:
        print("🔍 Checking if API is running...")
        is_running = asyncio.run(validate_running_api())
        if is_running:
            print("✅ API is running at http://localhost:8000")
        else:
            print(
                "⚠️  API is not running. Documentation will be generated from code only."
            )

    try:
        # Initialize generator
        generator = DocumentationGenerator(args.output_dir)

        # Generate documentation
        if args.format == "all":
            generated_files = generator.generate_all_formats()
        else:
            schema = generator.get_openapi_schema()
            generated_files = {}

            if args.format == "json":
                generated_files["json"] = generator.save_json_schema(schema)
            elif args.format == "yaml":
                generated_files["yaml"] = generator.save_yaml_schema(schema)
            elif args.format == "html":
                generated_files["html"] = generator.generate_html_docs(schema)
            elif args.format == "redoc":
                generated_files["redoc"] = generator.generate_redoc_html(schema)
            elif args.format == "postman":
                generated_files["postman"] = generator.generate_postman_collection(
                    schema
                )

        # Print summary
        print_summary(generated_files)

    except Exception as e:
        logger.error(f"Documentation generation failed: {e}")
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
