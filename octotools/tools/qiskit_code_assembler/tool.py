# octotools/tools/qiskit_code_assembler/tool.py
from typing import Any, Dict, List, Optional, Union
import os
from datetime import datetime
from octotools.tools.base import BaseTool
from octotools.models.semantic import SemanticCodeFragment
from octotools.models.semantic_types import SemanticTypes, topological_sort

class qiskit_Code_Assembler_Tool(BaseTool):
    """
    语义化代码组装工具 - 2.0版本
    将语义代码片段组装成完整的可执行Python文件
    """
    
    require_llm_engine = False
    
    # 新增语义属性
    semantic_type = SemanticTypes.COMPLETE_SOLUTION
    dependencies = [SemanticTypes.VQE_EXECUTION]  # 至少需要VQE执行代码
    provides = ["complete_code"]

    def __init__(self):
        super().__init__(
            tool_name="qiskit_Code_Assembler_Tool",
            tool_description="Assemble semantic code fragments into complete Qiskit solution.",
            tool_version="2.0.0",
            input_types={
                "semantic_fragments": "List[SemanticCodeFragment] - All code fragments to assemble",
                "code_fragments": "List[str] - Legacy string fragments (backward compatibility)",
                "solution_name": "str - Name for the solution (default: auto-generated)",
                "description": "str - Optional description for the solution",
                "save_file": "bool - Whether to save as .py file (default: True)"
            },
            output_type='SemanticCodeFragment - complete executable code',
            demo_commands=[
                {
                    "command": 'tool.execute(semantic_fragments=fragments)',
                    "description": "Assemble semantic fragments into complete solution"
                },
                {
                    "command": 'tool.execute(semantic_fragments=fragments, solution_name="my_tfim_vqe")',
                    "description": "Assemble with custom solution name"
                }
            ],
            user_metadata={
                "routing": {
                    "task_type": "CodeAssembly",
                    "backend": "qiskit",
                    "model": "universal",
                    "position": "final",
                    "requires_llm_engine": False,
                    "consumes": ["semantic_fragments"],
                    "produces": [SemanticTypes.COMPLETE_SOLUTION]
                },
                "outputs": {
                    "output_type": "SemanticCodeFragment",
                    "semantic_type": SemanticTypes.COMPLETE_SOLUTION
                }
            }
        )

    def _extract_and_dedupe_imports(self, fragments: List[SemanticCodeFragment]) -> List[str]:
        """从语义片段中提取和去重import语句"""
        import_lines = set()
        
        for fragment in fragments:
            lines = fragment.code.split('\n')
            for line in lines:
                stripped = line.strip()
                if (stripped.startswith('import ') or 
                    stripped.startswith('from ') and 'import' in stripped):
                    import_lines.add(stripped)
        
        # 排序imports：标准库优先，然后第三方库
        standard_imports = []
        third_party_imports = []
        
        for imp in sorted(import_lines):
            if any(lib in imp for lib in ['qiskit', 'numpy', 'scipy']):
                third_party_imports.append(imp)
            else:
                standard_imports.append(imp)
        
        # 合并并添加分隔
        all_imports = []
        if standard_imports:
            all_imports.extend(standard_imports)
        if third_party_imports:
            if standard_imports:
                all_imports.append('')  # 空行分隔
            all_imports.extend(third_party_imports)
        
        return all_imports

    def _remove_imports_from_fragment(self, code: str) -> str:
        """从代码片段中移除import语句"""
        lines = code.split('\n')
        filtered_lines = []
        
        for line in lines:
            stripped = line.strip()
            if (not stripped.startswith('import ') and 
                not (stripped.startswith('from ') and 'import' in stripped)):
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines).strip()

    def _sort_fragments_by_dependencies(self, fragments: List[SemanticCodeFragment]) -> List[SemanticCodeFragment]:
        """按语义依赖关系排序片段"""
        # 提取语义类型
        fragment_types = [f.semantic_type for f in fragments]
        
        # 拓扑排序
        sorted_types = topological_sort(fragment_types)
        
        # 按排序结果重新组织片段
        type_to_fragment = {f.semantic_type: f for f in fragments}
        sorted_fragments = []
        
        for stype in sorted_types:
            if stype in type_to_fragment:
                sorted_fragments.append(type_to_fragment[stype])
        
        return sorted_fragments

    def _generate_semantic_solution_header(self, solution_name: str, description: Optional[str], 
                                          fragments: List[SemanticCodeFragment]) -> str:
        """生成语义化的解决方案头部"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 统计片段信息
        fragment_info = []
        for fragment in fragments:
            fragment_info.append(f"  - {fragment.semantic_type}: {fragment.tool_source}")
        
        header = f'''#!/usr/bin/env python3
"""
{solution_name.replace('_', ' ').title()}
{description or 'Complete quantum computing solution generated by OctoTools'}

Generated by qiskit_Code_Assembler_Tool v2.0
Created: {timestamp}

Semantic Components:
{chr(10).join(fragment_info)}

This script contains a complete VQE workflow for quantum optimization.
All components are assembled from semantic code fragments.
"""

'''
        return header

    def _assemble_semantic_fragments(self, fragments: List[SemanticCodeFragment], 
                                   solution_name: str, description: Optional[str]) -> str:
        """组装语义代码片段为完整解决方案"""
        
        # 按依赖关系排序
        sorted_fragments = self._sort_fragments_by_dependencies(fragments)
        
        # 生成文件头
        header = self._generate_semantic_solution_header(solution_name, description, sorted_fragments)
        
        # 提取并合并imports
        imports = self._extract_and_dedupe_imports(sorted_fragments)
        imports_section = '\n'.join(imports) + '\n\n'
        
        # 组装代码段
        code_sections = [header, imports_section]
        
        # 添加主函数开始
        main_start = f'''if __name__ == "__main__":
    print("=" * 60)
    print("🐙 OctoTools - {solution_name.replace('_', ' ').title()}")
    print("=" * 60)
    print()
    
'''
        code_sections.append(main_start)
        
        # 添加每个语义片段（带缩进和注释）
        for i, fragment in enumerate(sorted_fragments):
            # 添加语义片段标识
            section_header = f'''    # ===== {fragment.semantic_type.upper()} SECTION =====
    # Generated by: {fragment.tool_source}
    # Provides: {", ".join(fragment.provides)}
    
'''
            code_sections.append(section_header)
            
            # 处理代码片段（移除imports，添加缩进）
            clean_code = self._remove_imports_from_fragment(fragment.code)
            indented_code = self._indent_code(clean_code, '    ')
            code_sections.append(indented_code)
            
            if i < len(sorted_fragments) - 1:
                code_sections.append('\n')  # 片段间添加空行
        
        # 添加主函数结尾
        main_end = '''
    print()
    print("=" * 60)
    print("🎉 Quantum solution completed successfully!")
    print("=" * 60)'''
        
        code_sections.append(main_end)
        
        return '\n'.join(code_sections)

    def _indent_code(self, code: str, indent: str) -> str:
        """给代码块添加缩进"""
        lines = code.split('\n')
        indented_lines = []
        
        for line in lines:
            if line.strip():  # 非空行才缩进
                indented_lines.append(indent + line)
            else:
                indented_lines.append('')
        
        return '\n'.join(indented_lines)

    def _save_code_to_file(self, code: str, solution_name: str, output_dir: str) -> str:
        """保存代码到Python文件"""
        filename = f"{solution_name}.py"
        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return os.path.abspath(file_path)

    def _legacy_assemble_code_fragments(self, code_fragments: List[str], 
                                      solution_name: str, description: Optional[str]) -> str:
        """向后兼容：组装字符串代码片段（保持原逻辑）"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f'''#!/usr/bin/env python3
"""
{solution_name.replace('_', ' ').title()}
{description or 'Qiskit VQE quantum computing solution'}

Generated by qiskit_Code_Assembler_Tool
Created: {timestamp}
"""

'''
        # 简单拼接（保持原有逻辑）
        return header + '\n\n'.join(code_fragments)

    def execute(
        self,
        semantic_fragments: Optional[List[SemanticCodeFragment]] = None,
        code_fragments: Optional[List[str]] = None,  # 向后兼容
        solution_name: Optional[str] = None,
        description: Optional[str] = None,
        save_file: bool = True
    ) -> SemanticCodeFragment:
        """
        组装代码片段为完整解决方案
        
        Args:
            semantic_fragments: 语义代码片段列表
            code_fragments: 字符串代码片段列表（向后兼容）
            solution_name: 解决方案名称
            description: 可选的解决方案描述
            save_file: 是否保存为.py文件
            
        Returns:
            SemanticCodeFragment: 完整解决方案的语义片段
        """
        
        # 验证输入
        if not semantic_fragments and not code_fragments:
            raise ValueError("Either semantic_fragments or code_fragments must be provided")
        
        # 生成解决方案名称
        if solution_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            solution_name = f"qiskit_vqe_solution_{timestamp}"
        
        # 组装完整代码
        if semantic_fragments:
            # 新的语义化组装
            complete_code = self._assemble_semantic_fragments(semantic_fragments, solution_name, description)
            assembly_mode = "semantic"
        else:
            # 向后兼容的字符串组装
            complete_code = self._legacy_assemble_code_fragments(code_fragments, solution_name, description)
            assembly_mode = "legacy"
        
        # 保存文件（如果需要）
        file_path = None
        if save_file:
            try:
                output_dir = getattr(self, 'output_dir', '.')
                file_path = self._save_code_to_file(complete_code, solution_name, output_dir)
            except Exception as e:
                print(f"Warning: Could not save file: {e}")
        
        # 返回语义片段
        return self.create_semantic_fragment(
            code=complete_code,
            variable_name="complete_code",
            metadata={
                "backend": "qiskit",
                "solution_name": solution_name,
                "assembly_mode": assembly_mode,
                "fragments_count": len(semantic_fragments) if semantic_fragments else len(code_fragments),
                "file_path": file_path,
                "generated_at": datetime.now().isoformat()
            }
        )