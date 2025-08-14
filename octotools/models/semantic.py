# octotools/models/semantic.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class SemanticCodeFragment:
    """语义化代码片段的核心数据结构"""
    code: str   # 实际的Python代码，可以直接exec()执行
    semantic_type: str      # 语义类型标识
    variable_name: str      # 指示执行这段代码后，主要的结果存储在哪个变量中，其他片段可以通过这个变量名引用结果
    dependencies: List[str] = field(default_factory=list)       # 告诉LLM执行前必须先有spec片段，需要从spec片段的execution_context中获取spec_ir变量
    provides: List[str] = field(default_factory=list)           # 提供当前片段执行后的输出变量
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_source: str = ""
    
    # 运行时状态
    is_executed: bool = False
    execution_context: Optional[Dict] = None        #执行上下文，包含所有局部变量
    
    def __post_init__(self):
        """确保provides包含variable_name"""
        if self.variable_name and self.variable_name not in self.provides:
            self.provides.append(self.variable_name)