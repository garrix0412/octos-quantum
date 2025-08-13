# qiskit_code_assembler_tool.py

from typing import Any, Dict, List, Optional
import os
import time
from datetime import datetime

from octotools.tools.base import BaseTool

CONTRACT_VERSION = "code_assembler.qiskit/v1"

class qiskit_Code_Assembler_Tool(BaseTool):
    """
    Universal code assembler for Qiskit quantum computing solutions.
    Combines code fragments into a complete executable Python file.
    """
    
    require_llm_engine = False

    def __init__(self):
        super().__init__(
            tool_name="qiskit_Code_Assembler_Tool",
            tool_description="Assemble code fragments into complete Qiskit solution and save as .py file.",
            tool_version="1.0.0",
            input_types={
                "code_fragments": "list - List of code strings from previous tools",
                "solution_name": "str - Name for the solution (default: auto-generated)",
                "description": "str - Optional description for the solution",
                "save_file": "bool - Whether to save as .py file (default: True)",
                "output_dir": "str - Directory to save file (default: current directory)"
            },
            output_type='dict - {"Code": str, "FilePath": str?, "metadata": {...}}',
            demo_commands=[
                {
                    "command": 'tool.execute(code_fragments=[spec_code, ham_code, ansatz_code, opt_code, vqe_code])',
                    "description": "Assemble code fragments and save to auto-named file"
                },
                {
                    "command": 'tool.execute(code_fragments=[...], solution_name="my_tfim_vqe", description="4-qubit TFIM VQE")',
                    "description": "Assemble with custom name and description"
                }
            ],
            user_metadata={
                "routing": {
                    "task_type": "CodeAssembly",
                    "backend": "qiskit",
                    "model": "universal",
                    "position": "final",
                    "requires_llm_engine": False,
                    "consumes": ["CodeFragments"],
                    "produces": ["CompleteCode", "PythonFile"]
                },
                "inputs": {
                    "required_fields": ["code_fragments"],
                    "optional_fields": ["solution_name", "description", "save_file", "output_dir"],
                    "defaults": {
                        "save_file": True,
                        "output_dir": "."
                    }
                },
                "outputs": {
                    "output_type": "dict",
                    "artifacts": ["solution.py"],
                    "contract_version": CONTRACT_VERSION
                },
                "error_codes": [
                    "INVALID_CODE_FRAGMENTS",
                    "FILE_SAVE_ERROR",
                    "INVALID_OUTPUT_DIR"
                ],
                "execution_profile": {
                    "deterministic": True,
                    "idempotent": False,  # File names include timestamps
                    "side_effects": ["write:solution.py"]
                }
            }
        )

    def execute(
        self,
        code_fragments: List[str],
        solution_name: Optional[str] = None,
        description: Optional[str] = None,
        save_file: bool = True,
        output_dir: str = "."
    ) -> Dict[str, Any]:
        """
        Assemble code fragments into complete solution.
        
        Args:
            code_fragments: List of code strings from previous tools
            solution_name: Name for the solution file
            description: Optional description for the solution
            save_file: Whether to save as .py file
            output_dir: Directory to save the file
            
        Returns:
            dict: Complete code, optional file path, and metadata
        """
        
        # Validate inputs
        if not isinstance(code_fragments, list) or not code_fragments:
            raise ValueError("INVALID_CODE_FRAGMENTS")
        
        if save_file and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                raise ValueError(f"INVALID_OUTPUT_DIR: {str(e)}")
        
        # Generate solution name if not provided
        if solution_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            solution_name = f"qiskit_vqe_solution_{timestamp}"
        
        # Assemble complete code
        complete_code = self._assemble_code(code_fragments, solution_name, description)
        
        result = {
            "Code": complete_code,
            "metadata": {
                "backend": "qiskit",
                "code_type": "complete_solution",
                "solution_name": solution_name,
                "fragments_count": len(code_fragments),
                "generated_at": datetime.now().isoformat(),
                "contract_version": CONTRACT_VERSION
            }
        }
        
        # Save file if requested
        if save_file:
            try:
                file_path = self._save_code_to_file(complete_code, solution_name, output_dir)
                result["FilePath"] = file_path
                result["metadata"]["saved_to"] = file_path
            except Exception as e:
                raise ValueError(f"FILE_SAVE_ERROR: {str(e)}")
        
        return result

    def _assemble_code(self, code_fragments: List[str], solution_name: str, description: Optional[str]) -> str:
        """Assemble code fragments into complete solution"""
        
        # Generate file header
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f'''#!/usr/bin/env python3
"""
{solution_name.replace('_', ' ').title()}
{description or 'Qiskit VQE quantum computing solution'}

Generated by qiskit_Code_Assembler_Tool
Created: {timestamp}
"""

'''
        
        # Collect all imports
        imports = self._extract_and_dedupe_imports(code_fragments)
        
        # Combine imports
        imports_section = '\n'.join(imports) + '\n\n'
        
        # Process code fragments (remove import statements)
        processed_fragments = []
        for fragment in code_fragments:
            processed = self._remove_imports_from_fragment(fragment)
            if processed.strip():  # Only add non-empty fragments
                processed_fragments.append(processed)
        
        # Combine all code sections
        code_sections = [header, imports_section]
        
        # Add main execution wrapper
        main_start = '''if __name__ == "__main__":
    print("=" * 50)
    print(f"Running {solution_name.replace('_', ' ').title()}")
    print("=" * 50)
    print()
    
'''
        
        code_sections.append(main_start)
        
        # Add processed fragments with proper indentation
        for i, fragment in enumerate(processed_fragments):
            # Indent the fragment for main block
            indented_fragment = self._indent_code(fragment, '    ')
            code_sections.append(indented_fragment)
            
            if i < len(processed_fragments) - 1:
                code_sections.append('')  # Add spacing between fragments
        
        # Add main end
        main_end = '''
    print()
    print("=" * 50)
    print("Solution completed!")
    print("=" * 50)'''
        
        code_sections.append(main_end)
        
        return '\n'.join(code_sections)

    def _extract_and_dedupe_imports(self, code_fragments: List[str]) -> List[str]:
        """Extract and deduplicate import statements"""
        import_lines = set()
        
        for fragment in code_fragments:
            lines = fragment.split('\n')
            for line in lines:
                stripped = line.strip()
                if (stripped.startswith('import ') or 
                    stripped.startswith('from ') or
                    stripped.startswith('#') and 'import' in stripped):
                    
                    # Skip comment-only lines unless they're import-related
                    if stripped.startswith('#') and 'import' not in stripped.lower():
                        continue
                    
                    import_lines.add(stripped)
        
        # Sort imports: standard library first, then third-party
        standard_imports = []
        third_party_imports = []
        
        for imp in sorted(import_lines):
            if imp.startswith('#'):
                continue
                
            # Simple heuristic: qiskit imports are third-party
            if 'qiskit' in imp or 'numpy' in imp or 'scipy' in imp:
                third_party_imports.append(imp)
            else:
                standard_imports.append(imp)
        
        # Combine with proper spacing
        all_imports = []
        if standard_imports:
            all_imports.extend(standard_imports)
        if third_party_imports:
            if standard_imports:
                all_imports.append('')  # Blank line between groups
            all_imports.extend(third_party_imports)
        
        return all_imports

    def _remove_imports_from_fragment(self, fragment: str) -> str:
        """Remove import statements from a code fragment"""
        lines = fragment.split('\n')
        filtered_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip import lines and their comments
            if (not stripped.startswith('import ') and 
                not stripped.startswith('from ') and
                not (stripped.startswith('#') and 'import' in stripped.lower())):
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines).strip()

    def _indent_code(self, code: str, indent: str) -> str:
        """Add indentation to code block"""
        lines = code.split('\n')
        indented_lines = []
        
        for line in lines:
            if line.strip():  # Don't indent empty lines
                indented_lines.append(indent + line)
            else:
                indented_lines.append('')
        
        return '\n'.join(indented_lines)

    def _save_code_to_file(self, code: str, solution_name: str, output_dir: str) -> str:
        """Save code to Python file"""
        filename = f"{solution_name}.py"
        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return os.path.abspath(file_path)

    def get_metadata(self):
        metadata = super().get_metadata()
        return metadata