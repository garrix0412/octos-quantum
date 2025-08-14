# octotools/models/semantic_registry.py
from typing import Dict, List, Set, Tuple, Optional
from .semantic import SemanticCodeFragment
from .semantic_types import SemanticTypes

class SemanticRegistry:
    """语义片段注册和依赖管理 - 简化版本"""
    
    def __init__(self):
        self.fragments: Dict[str, SemanticCodeFragment] = {}
        self.dependencies = SemanticTypes.DEPENDENCIES
    
    def register_fragment(self, fragment: SemanticCodeFragment) -> None:
        """注册语义片段"""
        self.fragments[fragment.semantic_type] = fragment
        if hasattr(self, 'verbose') and self.verbose:
            print(f"✅ Registered semantic fragment: {fragment.semantic_type}")
    
    def get_fragment(self, semantic_type: str) -> Optional[SemanticCodeFragment]:
        """获取语义片段"""
        return self.fragments.get(semantic_type)
    
    def has_fragment(self, semantic_type: str) -> bool:
        """检查是否有特定类型的片段"""
        return semantic_type in self.fragments
    
    def check_dependencies(self, semantic_type: str) -> Tuple[bool, List[str]]:
        """检查依赖是否满足"""
        required = self.dependencies.get(semantic_type, [])
        missing = [dep for dep in required if dep not in self.fragments]
        return len(missing) == 0, missing
    
    def get_next_possible_types(self) -> List[str]:
        """获取当前可以生成的语义类型"""
        possible = []
        for semantic_type in self.dependencies.keys():
            if semantic_type not in self.fragments:
                is_ready, _ = self.check_dependencies(semantic_type)
                if is_ready:
                    possible.append(semantic_type)
        return possible
    
    def get_completion_status(self) -> Dict[str, bool]:
        """获取完成状态"""
        return {stype: stype in self.fragments 
                for stype in self.dependencies.keys()}
    
    def get_available_variables(self) -> Dict[str, any]:
        """获取所有可用变量（用于执行上下文注入）"""
        variables = {}
        for fragment in self.fragments.values():
            if fragment.execution_context:
                for var_name in fragment.provides:
                    if var_name in fragment.execution_context:
                        variables[var_name] = fragment.execution_context[var_name]
        return variables

# 为了向后兼容，保留原来的接口
class VariableRegistry(SemanticRegistry):
    """向后兼容的变量注册表"""
    
    def get_tool_outputs(self, tool_name: str) -> List[str]:
        """获取工具预期输出（兼容旧接口）"""
        semantic_mapping = SemanticTypes.TOOL_SEMANTIC_MAPPING
        semantic_type = semantic_mapping.get(tool_name)
        
        if isinstance(semantic_type, str):
            fragment = self.get_fragment(semantic_type)
            return fragment.provides if fragment else []
        elif isinstance(semantic_type, list):
            provides = []
            for stype in semantic_type:
                fragment = self.get_fragment(stype)
                if fragment:
                    provides.extend(fragment.provides)
            return provides
        return []
    
    def get_tool_inputs(self, tool_name: str) -> List[str]:
        """获取工具预期输入（兼容旧接口）"""
        semantic_mapping = SemanticTypes.TOOL_SEMANTIC_MAPPING
        semantic_type = semantic_mapping.get(tool_name)
        
        if isinstance(semantic_type, str):
            return self.dependencies.get(semantic_type, [])
        elif isinstance(semantic_type, list):
            inputs = set()
            for stype in semantic_type:
                inputs.update(self.dependencies.get(stype, []))
            return list(inputs)
        return []

# 全局实例
semantic_registry = SemanticRegistry()
variable_registry = VariableRegistry()  # 保持向后兼容