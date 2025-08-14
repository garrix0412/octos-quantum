# octotools/models/memory.py
from typing import Dict, Any, List, Union, Optional
import os
from datetime import datetime

from octotools.models.semantic import SemanticCodeFragment
from octotools.models.semantic_types import SemanticTypes

class Memory:
    """升级版内存管理器 - 语义感知 + 向后兼容"""

    def __init__(self):
        self.query: Optional[str] = None
        self.files: List[Dict[str, str]] = []
        
        # 原有的actions（向后兼容）
        self.actions: Dict[str, Dict[str, Any]] = {}
        
        # 新增：语义化存储
        self.semantic_fragments: Dict[str, SemanticCodeFragment] = {}
        self.semantic_workflow: List[str] = []  # 记录语义类型的执行顺序
        self.workflow_progress: Dict[str, bool] = {}
        
        # 初始化默认工作流状态
        self._init_workflow_progress()

    def _init_workflow_progress(self):
        """初始化工作流进度追踪"""
        for semantic_type in SemanticTypes.DEPENDENCIES.keys():
            self.workflow_progress[semantic_type] = False

    # ===== 向后兼容：原有方法 =====
    
    def set_query(self, query: str) -> None:
        """设置查询（保持原接口）"""
        if not isinstance(query, str):
            raise TypeError("Query must be a string")
        self.query = query

    def add_file(self, file_name: Union[str, List[str]], description: Union[str, List[str], None] = None) -> None:
        """添加文件（保持原逻辑）"""
        if isinstance(file_name, str):
            file_name = [file_name]
        
        if description is None:
            description = [self._get_default_description(fname) for fname in file_name]
        elif isinstance(description, str):
            description = [description]
        
        if len(file_name) != len(description):
            raise ValueError("The number of files and descriptions must match.")
        
        for fname, desc in zip(file_name, description):
            self.files.append({
                'file_name': fname,
                'description': desc
            })

    def add_action(self, step_count: int, tool_name: str, sub_goal: str, command: str, result: Any) -> None:
        """添加action（保持原接口，但增强语义处理）"""
        action = {
            'tool_name': tool_name,
            'sub_goal': sub_goal,
            'command': command,
            'result': result,
        }
        step_name = f"Action Step {step_count}"
        self.actions[step_name] = action
        
        # 新增：尝试从result中提取语义片段
        if isinstance(result, list) and len(result) > 0:
            if isinstance(result[0], SemanticCodeFragment):
                self.add_semantic_fragment(result[0], step_count, tool_name, sub_goal)

    def get_query(self) -> Optional[str]:
        """获取查询（保持原接口）"""
        return self.query

    def get_files(self) -> List[Dict[str, str]]:
        """获取文件（保持原接口）"""
        return self.files
    
    def get_actions(self) -> Dict[str, Dict[str, Any]]:
        """获取actions（保持原接口）"""
        return self.actions

    # ===== 新增：语义化方法 =====
    
    def add_semantic_fragment(self, fragment: SemanticCodeFragment, step_count: int = None, 
                            tool_name: str = None, sub_goal: str = None) -> None:
        """添加语义代码片段"""
        # 存储语义片段
        self.semantic_fragments[fragment.semantic_type] = fragment
        
        # 更新工作流进度
        self.workflow_progress[fragment.semantic_type] = True
        
        # 记录执行顺序
        if fragment.semantic_type not in self.semantic_workflow:
            self.semantic_workflow.append(fragment.semantic_type)
        
        # 向后兼容：也添加到actions中
        if step_count is not None:
            self.add_action(step_count, tool_name or fragment.tool_source, 
                          sub_goal or f"Generate {fragment.semantic_type} fragment",
                          f"Generated semantic fragment: {fragment.semantic_type}", fragment)

    def get_semantic_fragment(self, semantic_type: str) -> Optional[SemanticCodeFragment]:
        """获取特定类型的语义片段"""
        return self.semantic_fragments.get(semantic_type)

    def get_all_semantic_fragments(self) -> List[SemanticCodeFragment]:
        """获取所有语义片段（按执行顺序）"""
        fragments = []
        for semantic_type in self.semantic_workflow:
            if semantic_type in self.semantic_fragments:
                fragments.append(self.semantic_fragments[semantic_type])
        return fragments

    def get_semantic_fragments_by_types(self, semantic_types: List[str]) -> List[SemanticCodeFragment]:
        """按指定类型获取语义片段"""
        fragments = []
        for semantic_type in semantic_types:
            if semantic_type in self.semantic_fragments:
                fragments.append(self.semantic_fragments[semantic_type])
        return fragments

    def has_semantic_fragment(self, semantic_type: str) -> bool:
        """检查是否有特定类型的语义片段"""
        return semantic_type in self.semantic_fragments

    def get_workflow_progress(self) -> Dict[str, bool]:
        """获取工作流进度状态"""
        return self.workflow_progress.copy()

    def get_completion_percentage(self) -> float:
        """获取完成百分比"""
        completed = sum(1 for completed in self.workflow_progress.values() if completed)
        total = len(self.workflow_progress)
        return (completed / total) * 100 if total > 0 else 0

    def get_next_required_types(self) -> List[str]:
        """获取下一步需要的语义类型（基于依赖关系）"""
        completed_types = set(semantic_type for semantic_type, completed 
                            in self.workflow_progress.items() if completed)
        
        next_types = []
        for semantic_type, dependencies in SemanticTypes.DEPENDENCIES.items():
            if semantic_type not in completed_types:
                # 检查依赖是否都满足
                if all(dep in completed_types for dep in dependencies):
                    next_types.append(semantic_type)
        
        return next_types

    def get_missing_dependencies(self, semantic_type: str) -> List[str]:
        """获取特定类型缺失的依赖"""
        completed_types = set(semantic_type for semantic_type, completed 
                            in self.workflow_progress.items() if completed)
        
        required_deps = SemanticTypes.DEPENDENCIES.get(semantic_type, [])
        missing = [dep for dep in required_deps if dep not in completed_types]
        return missing

    def is_workflow_complete(self, required_types: List[str] = None) -> bool:
        """检查工作流是否完成"""
        if required_types is None:
            # 默认检查是否有完整解决方案
            return self.has_semantic_fragment(SemanticTypes.COMPLETE_SOLUTION)
        
        return all(self.has_semantic_fragment(stype) for stype in required_types)

    def get_semantic_summary(self) -> Dict[str, Any]:
        """获取语义状态摘要"""
        return {
            "total_fragments": len(self.semantic_fragments),
            "completed_types": list(self.semantic_fragments.keys()),
            "workflow_progress": self.workflow_progress,
            "execution_order": self.semantic_workflow,
            "completion_percentage": self.get_completion_percentage(),
            "next_required": self.get_next_required_types(),
            "is_complete": self.is_workflow_complete()
        }

    def generate_workflow_report(self) -> str:
        """生成工作流进度报告"""
        summary = self.get_semantic_summary()
        
        report_lines = [
            "=== Semantic Workflow Progress ===",
            f"Completion: {summary['completion_percentage']:.1f}%",
            f"Fragments Generated: {summary['total_fragments']}",
            "",
            "Progress by Type:"
        ]
        
        for semantic_type, completed in self.workflow_progress.items():
            status = "✅" if completed else "⏳"
            dependencies = SemanticTypes.DEPENDENCIES.get(semantic_type, [])
            dep_str = f" (depends on: {dependencies})" if dependencies else ""
            report_lines.append(f"  {status} {semantic_type}{dep_str}")
        
        if summary['next_required']:
            report_lines.extend([
                "",
                f"Next Required: {', '.join(summary['next_required'])}"
            ])
        
        if summary['is_complete']:
            report_lines.extend([
                "",
                "🎉 Workflow Complete! Full solution available."
            ])
        
        return "\n".join(report_lines)

    def export_semantic_fragments(self, output_dir: str = ".") -> str:
        """导出所有语义片段为单独文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = os.path.join(output_dir, f"semantic_fragments_{timestamp}")
        os.makedirs(export_dir, exist_ok=True)
        
        exported_files = []
        for fragment in self.get_all_semantic_fragments():
            filename = f"{fragment.semantic_type}_{fragment.tool_source}.py"
            filepath = os.path.join(export_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# {fragment.semantic_type.upper()} Fragment\n")
                f.write(f"# Generated by: {fragment.tool_source}\n")
                f.write(f"# Provides: {', '.join(fragment.provides)}\n")
                f.write(f"# Dependencies: {', '.join(fragment.dependencies)}\n\n")
                f.write(fragment.code)
            
            exported_files.append(filepath)
        
        return export_dir

    # ===== 辅助方法 =====
    
    def _get_default_description(self, file_name: str) -> str:
        """获取文件的默认描述（保持原逻辑）"""
        _, ext = os.path.splitext(file_name)
        ext = ext.lower()

        file_types = {
            'text': ['.txt', '.md'],
            'document': ['.pdf', '.doc', '.docx'],
            'code': ['.py', '.js', '.java', '.cpp', '.h'],
            'data': ['.json', '.csv', '.xml'],
            'spreadsheet': ['.xlsx', '.xls'],
            'presentation': ['.ppt', '.pptx'],
        }
        
        file_type_descriptions = {
            'text': "A text file ({ext} format) containing additional information related to the query",
            'document': "A document ({ext} format) with content relevant to the query",
            'code': "A source code file ({ext} format) potentially related to the query",
            'data': "A data file ({ext} format) containing structured data pertinent to the query",
            'spreadsheet': "A spreadsheet file ({ext} format) with tabular data relevant to the query",
            'presentation': "A presentation file ({ext} format) with slides related to the query",
        }

        for file_type, extensions in file_types.items():
            if ext in extensions:
                return file_type_descriptions[file_type].format(ext=ext[1:])

        return f"A file with {ext[1:]} extension, provided as context for the query"

    def __str__(self) -> str:
        """字符串表示"""
        return self.generate_workflow_report()