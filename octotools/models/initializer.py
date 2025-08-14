# octotools/models/initializer.py
import os
import sys
import importlib
import inspect
import traceback
from typing import Dict, Any, List, Tuple
import time
from octotools.models.semantic_types import SemanticTypes

class Initializer:
    def __init__(self, enabled_tools: List[str] = [], model_string: str = None, verbose: bool = False, vllm_config_path: str = None):
        self.toolbox_metadata = {}
        self.available_tools = []
        self.enabled_tools = enabled_tools
        self.load_all = self.enabled_tools == ["all"]
        self.model_string = model_string
        self.verbose = verbose
        self.vllm_server_process = None
        self.vllm_config_path = vllm_config_path
        
        # 新增：语义化工具信息
        self.semantic_tools_info = {}
        self.legacy_tools_info = {}
        
        print("\n==> Initializing octotools...")
        print(f"Enabled tools: {self.enabled_tools}")
        print(f"LLM engine name: {self.model_string}")
        self._set_up_tools()
        
        if model_string and model_string.startswith("vllm-"):
            self.setup_vllm_server()

    def get_project_root(self):
        current_dir = os.getcwd()
        while current_dir != '/':
            octotools_path = os.path.join(current_dir, 'octotools')
            if (os.path.exists(octotools_path) and 
                os.path.exists(os.path.join(current_dir, 'examples')) and
                os.path.exists(os.path.join(octotools_path, 'tools')) and
                os.path.exists(os.path.join(octotools_path, 'solver.py'))):
                return octotools_path
            current_dir = os.path.dirname(current_dir)
        raise Exception("Could not find octo project root")
        
    def load_tools_and_get_metadata(self) -> Dict[str, Any]:
        print("Loading tools and getting metadata...")
        self.toolbox_metadata = {}
        octotools_dir = self.get_project_root()
        tools_dir = os.path.join(octotools_dir, 'tools')        
        
        sys.path.insert(0, octotools_dir)
        sys.path.insert(0, os.path.dirname(octotools_dir))
        print(f"Updated Python path: {sys.path}")
        
        if not os.path.exists(tools_dir):
            print(f"Error: Tools directory does not exist: {tools_dir}")
            return self.toolbox_metadata

        for root, dirs, files in os.walk(tools_dir):
            if 'tool.py' in files and (self.load_all or os.path.basename(root) in self.available_tools):
                file = 'tool.py'
                module_path = os.path.join(root, file)
                module_name = os.path.splitext(file)[0]
                relative_path = os.path.relpath(module_path, octotools_dir)
                import_path = '.'.join(os.path.split(relative_path)).replace(os.sep, '.')[:-3]

                print(f"\n==> Attempting to import: {import_path}")
                try:
                    module = importlib.import_module(import_path)
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and name.endswith('Tool') and name != 'BaseTool':
                            print(f"Found tool class: {name}")
                            try:
                                # 检查工具是否需要LLM引擎
                                if hasattr(obj, 'require_llm_engine') and obj.require_llm_engine:
                                    tool_instance = obj(model_string=self.model_string)
                                else:
                                    tool_instance = obj()
                                
                                # 获取基础元数据
                                basic_metadata = {
                                    'tool_name': getattr(tool_instance, 'tool_name', 'Unknown'),
                                    'tool_description': getattr(tool_instance, 'tool_description', 'No description'),
                                    'tool_version': getattr(tool_instance, 'tool_version', 'Unknown'),
                                    'input_types': getattr(tool_instance, 'input_types', {}),
                                    'output_type': getattr(tool_instance, 'output_type', 'Unknown'),
                                    'demo_commands': getattr(tool_instance, 'demo_commands', []),
                                    'user_metadata': getattr(tool_instance, 'user_metadata', {}),
                                    'require_llm_engine': getattr(obj, 'require_llm_engine', False),
                                }
                                
                                # 新增：检测和添加语义信息
                                semantic_info = self._extract_semantic_info(tool_instance, name)
                                basic_metadata.update(semantic_info)
                                
                                self.toolbox_metadata[name] = basic_metadata
                                
                                # 分类工具
                                if semantic_info['is_semantic']:
                                    self.semantic_tools_info[name] = semantic_info
                                    if self.verbose:
                                        print(f"  🔗 Semantic tool detected: {name}")
                                        print(f"     Semantic type: {semantic_info['semantic_type']}")
                                        print(f"     Dependencies: {semantic_info['dependencies']}")
                                        print(f"     Provides: {semantic_info['provides']}")
                                else:
                                    self.legacy_tools_info[name] = basic_metadata
                                    if self.verbose:
                                        print(f"  📦 Legacy tool: {name}")
                                
                                if self.verbose:
                                    print(f"Metadata for {name}: {basic_metadata}")
                                    
                            except Exception as e:
                                print(f"Error instantiating {name}: {str(e)}")
                                
                except Exception as e:
                    print(f"Error loading module {module_name}: {str(e)}")
                    
        print(f"\n==> Total number of tools imported: {len(self.toolbox_metadata)}")
        print(f"    Semantic tools: {len(self.semantic_tools_info)}")
        print(f"    Legacy tools: {len(self.legacy_tools_info)}")

        return self.toolbox_metadata

    def _extract_semantic_info(self, tool_instance, tool_name: str) -> Dict[str, Any]:
        """提取工具的语义信息 - 基于属性检测，不依赖版本号"""
        semantic_info = {
            'is_semantic': False,
            'semantic_type': None,
            'dependencies': [],
            'provides': [],
        }
        
        # 检查是否有语义属性（这是真正的判断标准）
        has_semantic_type = hasattr(tool_instance, 'semantic_type')
        has_dependencies = hasattr(tool_instance, 'dependencies')
        has_provides = hasattr(tool_instance, 'provides')
        
        # 如果有任何语义属性，就认为是语义化工具
        if has_semantic_type or has_dependencies or has_provides:
            semantic_info['is_semantic'] = True
            semantic_info['semantic_type'] = getattr(tool_instance, 'semantic_type', None)
            semantic_info['dependencies'] = getattr(tool_instance, 'dependencies', [])
            semantic_info['provides'] = getattr(tool_instance, 'provides', [])
            
        # 如果工具没有直接定义语义信息，但在映射表中，也认为是语义化的
        elif tool_name in SemanticTypes.TOOL_SEMANTIC_MAPPING:
            semantic_info['is_semantic'] = True
            mapped_type = SemanticTypes.TOOL_SEMANTIC_MAPPING[tool_name]
            
            if isinstance(mapped_type, str):
                semantic_info['semantic_type'] = mapped_type
                semantic_info['dependencies'] = SemanticTypes.DEPENDENCIES.get(mapped_type, [])
            elif isinstance(mapped_type, list):
                semantic_info['semantic_type'] = mapped_type[0]  # 使用第一个作为主要类型
                semantic_info['dependencies'] = SemanticTypes.DEPENDENCIES.get(mapped_type[0], [])
        
        return semantic_info

    def run_demo_commands(self) -> List[str]:
        print("\n==> Running demo commands for each tool...")
        self.available_tools = []

        for tool_name, tool_data in self.toolbox_metadata.items():
            print(f"Checking availability of {tool_name}...")

            try:
                module_name = f"tools.{tool_name.lower().replace('_tool', '')}.tool"
                module = importlib.import_module(module_name)
                tool_class = getattr(module, tool_name)
                tool_instance = tool_class()

                # 检查工具类型
                if tool_data.get('is_semantic', False):
                    if self.verbose:
                        print(f"  ✅ Semantic tool {tool_name} ready")
                else:
                    if self.verbose:
                        print(f"  ✅ Legacy tool {tool_name} ready")

                self.available_tools.append(tool_name)

            except Exception as e:
                print(f"Error checking availability of {tool_name}: {str(e)}")
                if self.verbose:
                    print(traceback.format_exc())

        # 更新工具元数据，只保留可用的工具
        self.toolbox_metadata = {tool: self.toolbox_metadata[tool] for tool in self.available_tools}
        
        print("\n✅ Finished running demo commands for each tool.")
        return self.available_tools
    
    def _set_up_tools(self) -> None:
        print("\n==> Setting up tools...")

        # 保持启用的工具
        self.available_tools = [tool.lower().replace('_tool', '') for tool in self.enabled_tools]
        
        # 加载工具并获取元数据
        self.load_tools_and_get_metadata()
        
        # 运行demo命令确定可用工具
        self.run_demo_commands()
        
        # 过滤工具箱元数据，只包含可用工具
        self.toolbox_metadata = {tool: self.toolbox_metadata[tool] for tool in self.available_tools}
        
        print("✅ Finished setting up tools.")
        print(f"✅ Total number of final available tools: {len(self.available_tools)}")
        print(f"✅ Final available tools: {self.available_tools}")
        
        # 输出语义化统计
        semantic_count = len([tool for tool in self.available_tools 
                            if self.toolbox_metadata[tool].get('is_semantic', False)])
        legacy_count = len(self.available_tools) - semantic_count
        
        print(f"   📊 Semantic tools: {semantic_count}")
        print(f"   📊 Legacy tools: {legacy_count}")

    def get_semantic_workflow_info(self) -> Dict[str, Any]:
        """获取语义工作流信息"""
        semantic_tools = {name: info for name, info in self.semantic_tools_info.items() 
                         if name in self.available_tools}
        
        workflow_info = {
            'available_semantic_types': list(set(
                tool['semantic_type'] for tool in semantic_tools.values() 
                if tool['semantic_type']
            )),
            'semantic_dependencies': SemanticTypes.DEPENDENCIES,
            'tool_semantic_mapping': {name: tool['semantic_type'] 
                                    for name, tool in semantic_tools.items() 
                                    if tool['semantic_type']},
            'semantic_tools': semantic_tools,
            'legacy_tools': {name: info for name, info in self.legacy_tools_info.items() 
                           if name in self.available_tools}
        }
        
        return workflow_info

    def get_tools_by_semantic_type(self, semantic_type: str) -> List[str]:
        """根据语义类型获取工具列表"""
        matching_tools = []
        for tool_name in self.available_tools:
            tool_metadata = self.toolbox_metadata.get(tool_name, {})
            if tool_metadata.get('semantic_type') == semantic_type:
                matching_tools.append(tool_name)
        return matching_tools

    def validate_semantic_workflow(self, required_types: List[str]) -> Dict[str, Any]:
        """验证是否可以执行指定的语义工作流"""
        available_types = set(
            self.toolbox_metadata[tool].get('semantic_type') 
            for tool in self.available_tools
            if self.toolbox_metadata[tool].get('semantic_type')
        )
        
        missing_types = set(required_types) - available_types
        
        validation_result = {
            'is_valid': len(missing_types) == 0,
            'available_types': list(available_types),
            'required_types': required_types,
            'missing_types': list(missing_types),
            'recommendations': []
        }
        
        if missing_types:
            validation_result['recommendations'] = [
                f"Enable tools that provide semantic type: {missing_type}" 
                for missing_type in missing_types
            ]
        
        return validation_result

    def setup_vllm_server(self) -> None:
        # 保持原有的VLLM服务器设置逻辑
        try:
            import vllm
        except ImportError:
            raise ImportError("If you'd like to use VLLM models, please install the vllm package by running `pip install vllm`.")
        
        if self.vllm_config_path is not None and not os.path.exists(self.vllm_config_path):
            raise ValueError(f"VLLM config path does not exist: {self.vllm_config_path}")
            
        command = ["vllm", "serve", self.model_string.replace("vllm-", ""), "--port", "8888"]
        if self.vllm_config_path is not None:
            command = ["vllm", "serve", "--config", self.vllm_config_path, "--port", "8888"]

        import subprocess
        vllm_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        print("Starting VLLM server...")
        while True:
            output = vllm_process.stdout.readline()
            error = vllm_process.stderr.readline()
            time.sleep(5)
            if output.strip() != "":
                print("VLLM server standard output:", output.strip())
            if error.strip() != "":
                print("VLLM server standard error:", error.strip())

            if "Application startup complete." in output or "Application startup complete." in error:
                print("VLLM server started successfully.")
                break

            if vllm_process.poll() is not None:
                print("VLLM server process terminated unexpectedly. Please check the output above for more information.")
                break

        self.vllm_server_process = vllm_process

if __name__ == "__main__":
    enabled_tools = ["Generalist_Solution_Generator_Tool"]
    initializer = Initializer(enabled_tools=enabled_tools)

    print("\nAvailable tools:")
    print(initializer.available_tools)

    print("\nToolbox metadata for available tools:")
    print(initializer.toolbox_metadata)
    
    print("\nSemantic workflow info:")
    print(initializer.get_semantic_workflow_info())