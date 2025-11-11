import json
from mcp.types import InitializeRequestParams
print(json.dumps(InitializeRequestParams.model_json_schema(), indent=2))
