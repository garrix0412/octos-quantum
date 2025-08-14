# octotools/tools/base.py
from typing import Any, Dict, List, Optional, Union
from octotools.engine.openai import ChatOpenAI
from octotools.models.semantic import SemanticCodeFragment
from octotools.models.semantic_types import SemanticTypes

class BaseTool:
    """
    升级版BaseTool，支持语义化代码片段生成
    保持向后兼容
    """

    require_llm_engine = False

    def __init__(self, tool_name=None, tool_description=None, tool_version=None, 
                 input_types=None, output_type=None, demo_commands=None, 
                 output_dir=None, user_metadata=None, model_string=None):
        
        # 原有属性保持不变
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.tool_version = tool_version
        self.input_types = input_types
        self.output_type = output_type
        self.demo_commands = demo_commands
        self.output_dir = output_dir
        self.user_metadata = user_metadata
        self.model_string = model_string
        
        # 新增语义化属性
        self.semantic_type = getattr(self, 'semantic_type', None)
        self.dependencies = getattr(self, 'dependencies', [])
        self.provides = getattr(self, 'provides', [])

    def set_metadata(self, tool_name, tool_description, tool_version, input_types, output_type, demo_commands, user_metadata=None):
        """保持原有接口不变"""
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.tool_version = tool_version
        self.input_types = input_types
        self.output_type = output_type
        self.demo_commands = demo_commands
        self.user_metadata = user_metadata

    def get_metadata(self):
        """保持原有接口，添加语义信息"""
        metadata = {
            "tool_name": self.tool_name,
            "tool_description": self.tool_description,
            "tool_version": self.tool_version,
            "input_types": self.input_types,
            "output_type": self.output_type,
            "demo_commands": self.demo_commands,
            "require_llm_engine": self.require_llm_engine,
        }
        if self.user_metadata:
            metadata["user_metadata"] = self.user_metadata
            
        # 添加语义信息
        if self.semantic_type:
            metadata["semantic_type"] = self.semantic_type
            metadata["dependencies"] = self.dependencies
            metadata["provides"] = self.provides
            
        return metadata

    def set_custom_output_dir(self, output_dir):
        """保持原有接口不变"""
        self.output_dir = output_dir

    def set_llm_engine(self, model_string):
        """保持原有接口不变"""
        self.model_string = model_string

    def execute(self, *args, **kwargs):
        """原有的execute方法，子类必须实现"""
        raise NotImplementedError("Subclasses must implement the execute method.")
    
    # ===== 新增语义化支持方法 =====
    
    def create_semantic_fragment(self, code: str, variable_name: str, 
                                metadata: Optional[Dict] = None) -> SemanticCodeFragment:
        """创建语义代码片段的辅助方法"""
        if not self.semantic_type:
            raise ValueError(f"Tool {self.tool_name} must define semantic_type to create semantic fragments")
            
        return SemanticCodeFragment(
            code=code,
            semantic_type=self.semantic_type,
            variable_name=variable_name,
            dependencies=self.dependencies,
            provides=self.provides if self.provides else [variable_name],
            metadata=metadata or {},
            tool_source=self.tool_name
        )
    
    def wrap_legacy_result(self, result: Any) -> SemanticCodeFragment:
        """将旧格式结果包装为语义片段"""
        if isinstance(result, SemanticCodeFragment):
            return result
            
        if isinstance(result, dict) and "Code" in result:
            # 现有工具的标准格式
            code = result["Code"]
            metadata = result.get("metadata", {})
            
            # 从工具映射中获取语义类型
            tool_mapping = SemanticTypes.TOOL_SEMANTIC_MAPPING
            mapped_type = tool_mapping.get(self.tool_name)
            
            if isinstance(mapped_type, str):
                semantic_type = mapped_type
                # 根据语义类型推断变量名
                variable_name = self._infer_variable_name(semantic_type)
            else:
                # 如果没有映射，使用默认值
                semantic_type = "unknown"
                variable_name = "result"
            
            return SemanticCodeFragment(
                code=code,
                semantic_type=semantic_type,
                variable_name=variable_name,
                dependencies=[],
                provides=[variable_name],
                metadata=metadata,
                tool_source=self.tool_name
            )
        
        # 其他格式暂时不支持
        raise ValueError(f"Cannot wrap result of type {type(result)} from tool {self.tool_name}")
    
    def _infer_variable_name(self, semantic_type: str) -> str:
        """根据语义类型推断变量名"""
        type_to_var = {
            SemanticTypes.SPEC: "spec_ir",
            SemanticTypes.HAMILTONIAN: "hamiltonian",
            SemanticTypes.ANSATZ: "ansatz",
            SemanticTypes.OPTIMIZER: "optimizer",
            SemanticTypes.ESTIMATOR: "estimator",
            SemanticTypes.VQE_EXECUTION: "vqe_result",
            SemanticTypes.COMPLETE_SOLUTION: "complete_code"
        }
        return type_to_var.get(semantic_type, "result")