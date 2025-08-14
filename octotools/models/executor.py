# octotools/models/executor.py
import importlib
import json
import os
import re
import signal
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from octotools.engine.factory import create_llm_engine
from octotools.models.formatters import ToolCommand
from octotools.models.semantic import SemanticCodeFragment
from octotools.models.semantic_registry import SemanticRegistry
from octotools.models.semantic_types import SemanticTypes

try:
    TimeoutError
except NameError:
    class TimeoutError(Exception):
        pass

def timeout_handler(signum, frame):
    raise TimeoutError("Function execution timed out")

class SemanticExecutor:
    def __init__(self, llm_engine_name: str, root_cache_dir: str = "solver_cache", 
                 num_threads: int = 1, max_time: int = 120, max_output_length: int = 100000, 
                 verbose: bool = False):
        self.llm_engine_name = llm_engine_name
        self.root_cache_dir = root_cache_dir
        self.num_threads = num_threads
        self.max_time = max_time
        self.max_output_length = max_output_length
        self.verbose = verbose
        
        self.semantic_registry = SemanticRegistry()
        self.semantic_registry.verbose = verbose
        
        self.global_variables = {}

    def set_query_cache_dir(self, query_cache_dir):
        if query_cache_dir:
            self.query_cache_dir = query_cache_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.query_cache_dir = os.path.join(self.root_cache_dir, timestamp)
        os.makedirs(self.query_cache_dir, exist_ok=True)

    def register_semantic_fragment(self, fragment: SemanticCodeFragment):
        self.semantic_registry.register_fragment(fragment)
        self._execute_fragment_for_variables(fragment)
        
        if self.verbose:
            print(f"✅ Registered and executed semantic fragment: {fragment.semantic_type}")

    def _execute_fragment_for_variables(self, fragment: SemanticCodeFragment):
        try:
            execution_context = {**self.global_variables}
            exec(fragment.code, globals(), execution_context)
            
            for var_name in fragment.provides:
                if var_name in execution_context:
                    self.global_variables[var_name] = execution_context[var_name]
                    if self.verbose:
                        print(f"  📝 Extracted variable: {var_name}")
            
            fragment.execution_context = execution_context
            fragment.is_executed = True
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Warning: Failed to execute fragment {fragment.semantic_type}: {e}")

    def generate_tool_command(self, question: str, image: str, context: str, sub_goal: str, 
                            tool_name: str, tool_metadata: Dict[str, Any]) -> Any:
        
        semantic_status = self.semantic_registry.get_completion_status()
        available_fragments = list(self.semantic_registry.fragments.keys())
        next_possible = self.semantic_registry.get_next_possible_types()
        
        prompt_generate_tool_command = f"""
Task: Generate a precise command to execute the selected tool based on semantic context.

Query: {question}
Context: {context}
Sub-Goal: {sub_goal}
Selected Tool: {tool_name}
Tool Metadata: {tool_metadata}

Semantic Context:
- Available semantic fragments: {available_fragments}
- Completion status: {semantic_status}
- Next possible types: {next_possible}
- Available variables: {list(self.global_variables.keys())}

Instructions:
1. This is a SEMANTIC CODE GENERATION system - tools generate code fragments, not data objects
2. If the tool supports semantic fragments (v2.0+), prefer using semantic fragment inputs
3. Each tool generates a SemanticCodeFragment containing executable code
4. Variables are available from previously executed fragments: {list(self.global_variables.keys())}
5. For new tools (v2.0), the primary input is usually a semantic fragment from previous steps
6. For legacy compatibility, tools may still accept direct dictionary inputs

Tool Input Patterns:
- Spec Tool: Basic parameters → generates spec_ir code
- Hamiltonian Tool: spec_fragment=spec → generates hamiltonian code  
- Ansatz Tool: spec_fragment=spec → generates ansatz code
- Optimizer Tool: spec_fragment=spec → generates optimizer+estimator code
- VQE Tool: semantic_fragments=semantic_fragments → generates VQE execution code
- Code Assembler: semantic_fragments=semantic_fragments → generates complete solution

Output Format:
Analysis: <analysis>
Command Explanation: <explanation>
Generated Command:
```python
execution = tool.execute(parameter=value)

MANDATORY FORMATTING RULES:
1. ALWAYS use format: execution = tool.execute(...)
2. NEVER use: tool.execute(...) without execution assignment
3. NEVER use: ClassName.execute(...) static method calls
4. Use instance method only: tool.execute(...)
5. Available semantic variables: spec, hamiltonian, ansatz, optimizer, estimator
6. For fragments list: semantic_fragments=semantic_fragments

CORRECT Examples:
✅ execution = tool.execute(model='TFIM', N=8)
✅ execution = tool.execute(spec_fragment=spec)
✅ execution = tool.execute(semantic_fragments=semantic_fragments)

INCORRECT Examples:
❌ tool.execute(spec_fragment=spec)
❌ result = tool.execute(spec_fragment=spec)❌ execution = {tool_name}.execute(...)
❌ {tool_name}.execute(...)
"""

        llm_generate_tool_command = create_llm_engine(model_string=self.llm_engine_name, is_multimodal=False)
        tool_command = llm_generate_tool_command(prompt_generate_tool_command, response_format=ToolCommand)

        return tool_command

    def extract_explanation_and_command(self, response: Any) -> tuple:
        def normalize_code(code: str) -> str:
            return re.sub(r'^```python\s*', '', code).rstrip('```').strip()

        if isinstance(response, str):
            try:
                response_dict = json.loads(response)
                response = ToolCommand(**response_dict)
            except Exception as e:
                print(f"Failed to parse response as JSON: {str(e)}")
                
        if isinstance(response, ToolCommand):
            analysis = response.analysis.strip()
            explanation = response.explanation.strip()
            command = response.command.strip()
        else:
            analysis_pattern = r"Analysis:(.*?)Command Explanation"
            analysis_match = re.search(analysis_pattern, response, re.DOTALL)
            analysis = analysis_match.group(1).strip() if analysis_match else "No analysis found."
            
            explanation_pattern = r"Command Explanation:(.*?)Generated Command"
            explanation_match = re.search(explanation_pattern, response, re.DOTALL)
            explanation = explanation_match.group(1).strip() if explanation_match else "No explanation found."
            
            command_pattern = r"Generated Command:.*?```python\n(.*?)```"
            command_match = re.search(command_pattern, response, re.DOTALL)
            command = command_match.group(1).strip() if command_match else "No command found."

        command = normalize_code(command)
        return analysis, explanation, command

    def execute_tool_command(self, tool_name: str, command: str) -> Any:
        
        def split_commands(command: str) -> List[str]:
            pattern = r'.*?execution\s*=\s*tool\.execute\([^\n]*\)\s*(?:\n|$)'
            blocks = re.findall(pattern, command, re.DOTALL)
            return [block.strip() for block in blocks if block.strip()]

        def execute_with_timeout(block: str, local_context: dict) -> Optional[Any]:
            enhanced_context = {
                'tool': tool,
                **self.global_variables,
                **local_context,
                **self._build_semantic_context()
            }
            
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.max_time)

            try:
                exec(block, globals(), enhanced_context)
                result = enhanced_context.get('execution')
                
                if isinstance(result, SemanticCodeFragment):
                    self.register_semantic_fragment(result)
                elif isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], dict):
                        wrapped_fragment = self._wrap_legacy_result(result[0], tool_name)
                        if wrapped_fragment:
                            self.register_semantic_fragment(wrapped_fragment)
                
                signal.alarm(0)
                return result
                
            except TimeoutError:
                return f"Execution timed out after {self.max_time} seconds"
            finally:
                signal.alarm(0)

        try:
            module_name = f"tools.{tool_name.lower().replace('_tool', '')}.tool"
            module = importlib.import_module(module_name)
            tool_class = getattr(module, tool_name)

            if getattr(tool_class, 'require_llm_engine', False):
                tool = tool_class(model_string=self.llm_engine_name)
            else:
                tool = tool_class()

            tool.set_custom_output_dir(self.query_cache_dir)

            command_blocks = split_commands(command)
            executions = []

            for block in command_blocks:
                local_context = {'tool': tool}
                result = execute_with_timeout(block, local_context)
                
                if result is not None:
                    executions.append(result)
                else:
                    executions.append(f"No execution captured from block: {block}")

            return executions
            
        except Exception as e:
            return f"Error in execute_tool_command: {str(e)}"

    def _build_semantic_context(self) -> Dict[str, Any]:
        """
        构建语义上下文，供工具执行时使用。
        
        修复说明（2024-01-13）：
        问题根源：之前只创建了 {type}_fragment 变量，没有创建简化的 {type} 变量，
                导致执行命令如 tool.execute(spec_fragment=spec) 时出现 "name 'spec' is not defined" 错误。
        
        修复方案：
        1. 为每个语义片段创建多个引用，确保不同命名风格都能访问
        2. 从片段的执行上下文中提取实际的变量值
        3. 添加调试信息便于追踪问题
        """
        context = {}
        
        for semantic_type, fragment in self.semantic_registry.fragments.items():
            # 修复1：添加 {type}_fragment 引用（保持向后兼容）
            # 例如：spec_fragment -> SemanticCodeFragment 对象
            context[f"{semantic_type}_fragment"] = fragment
            
            # 修复2：添加简化的 {type} 引用（解决 "name 'spec' is not defined" 错误）
            # 例如：spec -> SemanticCodeFragment 对象
            # 这样 tool.execute(spec_fragment=spec) 就能正确找到 spec 变量
            context[semantic_type] = fragment
            
            # 修复3：从片段的执行上下文中提取实际变量
            # 例如：spec_ir -> 实际的字典数据
            if fragment.execution_context:
                for var_name in fragment.provides:
                    if var_name in fragment.execution_context:
                        # 将片段执行后产生的变量添加到上下文
                        # 这样可以直接访问 spec_ir, hamiltonian 等具体数据
                        context[var_name] = fragment.execution_context[var_name]
            
            # 修复4：额外保险 - 确保所有执行上下文的有效变量都可访问
            if fragment.execution_context:
                for var_name, var_value in fragment.execution_context.items():
                    # 跳过内置变量，避免污染上下文
                    if not var_name.startswith('__') and var_name not in ['builtins', 'globals', 'locals']:
                        # 如果变量还没被添加，则添加它
                        if var_name not in context:
                            context[var_name] = var_value
        
        # 保持原有功能：添加所有片段的列表
        context['semantic_fragments'] = list(self.semantic_registry.fragments.values())
        
        # 修复5：添加调试信息，帮助追踪可用变量
        if hasattr(self, 'verbose') and self.verbose:
            # 过滤掉内部变量，只显示用户相关的变量
            available_vars = [k for k in context.keys() 
                            if not k.startswith('_') and k != 'semantic_fragments']
            if available_vars:
                print(f"  📌 Semantic context variables: {sorted(available_vars)}")
        
        return context

    def _wrap_legacy_result(self, result: Dict[str, Any], tool_name: str) -> Optional[SemanticCodeFragment]:
        try:
            tool_mapping = SemanticTypes.TOOL_SEMANTIC_MAPPING
            semantic_type = tool_mapping.get(tool_name)
            
            if not semantic_type or "Code" not in result:
                return None
            
            if isinstance(semantic_type, list):
                semantic_type = semantic_type[0]
            
            var_name_map = {
                SemanticTypes.SPEC: "spec_ir",
                SemanticTypes.HAMILTONIAN: "hamiltonian", 
                SemanticTypes.ANSATZ: "ansatz",
                SemanticTypes.OPTIMIZER: "optimizer",
                SemanticTypes.VQE_EXECUTION: "vqe_result"
            }
            
            variable_name = var_name_map.get(semantic_type, "result")
            
            fragment = SemanticCodeFragment(
                code=result["Code"],
                semantic_type=semantic_type,
                variable_name=variable_name,
                dependencies=SemanticTypes.DEPENDENCIES.get(semantic_type, []),
                provides=[variable_name],
                metadata=result.get("metadata", {}),
                tool_source=tool_name
            )
            
            return fragment
            
        except Exception as e:
            if self.verbose:
                print(f"Failed to wrap legacy result: {e}")
            return None

    def get_semantic_status(self) -> Dict[str, Any]:
        return {
            "completed_types": list(self.semantic_registry.fragments.keys()),
            "completion_status": self.semantic_registry.get_completion_status(),
            "next_possible": self.semantic_registry.get_next_possible_types(),
            "available_variables": list(self.global_variables.keys()),
            "total_fragments": len(self.semantic_registry.fragments)
        }

class Executor(SemanticExecutor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'verbose') and self.verbose:
            print("🔄 Using backward-compatible Executor (with semantic support)")
