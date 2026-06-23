import json
from models.response_models import RepoMap, ProjectDoc, ModuleDoc, APIDoc
from core.llm_client import LLMClient
from utils.logger import get_logger

logger = get_logger(__name__)

class DocGenerator:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def generate_project_docs(self, repo_map: RepoMap) -> ProjectDoc:
        prompt = f"""You are an expert technical writer.
Analyze this repository map and provide a project overview.
Languages: {repo_map.detected_languages}
Frameworks: {repo_map.detected_frameworks}
Files: {repo_map.files}

Return valid JSON format matching this structure:
{{
    "tech_stack": "Summary of languages and frameworks",
    "architecture_summary": "High-level description of how the project is structured",
    "entry_points": ["list of main entry point files"]
}}"""
        try:
            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            data = json.loads(response.choices[0].message.content)
            
            return ProjectDoc(
                tech_stack=data.get("tech_stack", ""),
                architecture_summary=data.get("architecture_summary", ""),
                entry_points=data.get("entry_points", []),
                modules=[],
                api_routes=[]
            )
        except Exception as e:
            logger.error(f"Error generating project docs: {e}")
            return ProjectDoc(tech_stack="", architecture_summary="", entry_points=[], modules=[], api_routes=[])

    async def generate_module_docs(self, module_path: str, file_list: list) -> ModuleDoc:
        prompt = f"""You are an expert technical writer.
Summarize the purpose of the following module and list its likely public functions based on these files: {file_list}.
Return valid JSON format matching this structure:
{{
    "purpose": "2-3 sentences explaining the module's purpose",
    "public_functions": [
        {{"name": "func_name", "description": "what it does"}}
    ],
    "dependencies": ["list of internal or external dependencies"]
}}"""
        try:
            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            data = json.loads(response.choices[0].message.content)
            return ModuleDoc(
                module_path=module_path,
                purpose=data.get("purpose", ""),
                public_functions=data.get("public_functions", []),
                dependencies=data.get("dependencies", [])
            )
        except Exception as e:
            logger.error(f"Error generating module docs for {module_path}: {e}")
            return ModuleDoc(module_path=module_path, purpose="", public_functions=[], dependencies=[])
