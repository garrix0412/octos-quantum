# octotools/solver.py
import os
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from octotools.models.initializer import Initializer
from octotools.models.planner import Planner
from octotools.models.executor import SemanticExecutor
from octotools.models.memory import Memory
from octotools.models.semantic_registry import SemanticRegistry
from octotools.models.semantic_types import SemanticTypes
from octotools.models.utils import make_json_serializable_truncated

class SemanticSolver:
    """升级版语义感知求解器"""
    
    def __init__(
        self,
        llm_engine_name: str,
        enabled_tools: List[str] = ["all"],
        output_types: str = "final,direct",
        max_steps: int = 10,
        max_time: int = 300,
        max_tokens: int = 4000,
        root_cache_dir: str = "solver_cache",
        verbose: bool = False
    ):
        self.llm_engine_name = llm_engine_name
        self.enabled_tools = enabled_tools
        self.output_types = output_types.split(",") if isinstance(output_types, str) else output_types
        self.max_steps = max_steps
        self.max_time = max_time
        self.max_tokens = max_tokens
        self.root_cache_dir = root_cache_dir
        self.verbose = verbose
        
        # 初始化工具
        self.initializer = Initializer(
            enabled_tools=enabled_tools,
            model_string=llm_engine_name,
            verbose=verbose
        )
        
        # 核心组件
        self.semantic_registry = SemanticRegistry()
        self.memory = Memory()
        
        # 初始化规划器
        self.planner = Planner(
            llm_engine_name=llm_engine_name,
            toolbox_metadata=self.initializer.toolbox_metadata,
            available_tools=self.initializer.available_tools,
            verbose=verbose
        )
        
        # 初始化执行器
        self.executor = SemanticExecutor(
            llm_engine_name=llm_engine_name,
            root_cache_dir=root_cache_dir,
            max_time=max_time,
            verbose=verbose
        )
        
        # 连接语义注册表
        self._connect_semantic_components()
        
        if verbose:
            print("🐙 SemanticSolver initialized with semantic awareness")

    def _connect_semantic_components(self):
        """连接语义化组件，确保它们共享状态"""
        # 所有组件共享同一个语义注册表
        self.planner.set_semantic_registry(self.semantic_registry)
        self.executor.semantic_registry = self.semantic_registry
        
        # 确保verbose设置一致
        if hasattr(self.semantic_registry, 'verbose'):
            self.semantic_registry.verbose = self.verbose

    def solve(self, question: str, image: str = "", files: List[str] = None) -> str:
        """主求解方法 - 语义感知版本"""
        
        if self.verbose:
            print(f"\n==> 🔍 Received Query: {question}")
        
        # 设置查询缓存目录
        query_cache_dir = self._setup_query_cache()
        self.executor.set_query_cache_dir(query_cache_dir)
        
        # 初始化内存
        self.memory.set_query(question)
        if files:
            self.memory.add_file(files)
        
        # 开始计时
        start_time = time.time()
        
        try:
            # 步骤1: 查询分析
            if self.verbose:
                print(f"\n==> 🐙 Reasoning Steps from OctoTools (Deep Thinking...)")
                print(f"\n==> 🔍 Step 0: Query Analysis")
            
            query_analysis_start = time.time()
            query_analysis = self.planner.analyze_query(question, image)
            
            if self.verbose:
                print(query_analysis)
                print(f"[Time]: {time.time() - query_analysis_start:.2f}s")
            
            # 主循环：语义感知的步骤执行
            step_count = 1
            while step_count <= self.max_steps:
                
                # 检查时间限制
                if time.time() - start_time > self.max_time:
                    if self.verbose:
                        print(f"\n==> ⏰ Time limit reached ({self.max_time}s)")
                    break
                
                # 生成下一步
                step_start_time = time.time()
                if self.verbose:
                    print(f"\n==> 🎯 Step {step_count}: Action Prediction")
                
                next_step = self.planner.generate_next_step(
                    question, image, query_analysis, self.memory, step_count, self.max_steps
                )
                
                # 提取步骤信息
                context, sub_goal, tool_name = self.planner.extract_context_subgoal_and_tool(next_step)
                
                if tool_name is None or "No matched tool" in tool_name:
                    if self.verbose:
                        print(f"\n==> ❌ Invalid tool selection: {tool_name}")
                    break
                
                if self.verbose:
                    print(f"\n[Context]: {context}")
                    print(f"[Sub Goal]: {sub_goal}")
                    print(f"[Tool]: {tool_name}")
                    print(f"[Time]: {time.time() - step_start_time:.2f}s")
                    
                    # 显示当前语义状态
                    semantic_status = self.semantic_registry.get_completion_status()
                    completed_types = [k for k, v in semantic_status.items() if v]
                    if completed_types:
                        print(f"[Semantic Progress]: {completed_types}")
                
                # 生成工具命令
                if self.verbose:
                    print(f"\n==> 📝 Step {step_count}: Command Generation ({tool_name})")
                
                command_start = time.time()
                tool_metadata = self.initializer.toolbox_metadata.get(tool_name, {})
                
                tool_command = self.executor.generate_tool_command(
                    question, image, context, sub_goal, tool_name, tool_metadata
                )
                
                analysis, explanation, command = self.executor.extract_explanation_and_command(tool_command)
                
                if self.verbose:
                    print(f"\n[Analysis]: {analysis}")
                    print(f"[Explanation]: {explanation}")
                    print(f"[Command]: {command}")
                    print(f"[Time]: {time.time() - command_start:.2f}s")
                
                # 执行命令
                if self.verbose:
                    print(f"\n==> 🛠️ Step {step_count}: Command Execution ({tool_name})")
                
                execution_start = time.time()
                
                # 检查工具是否可用
                if tool_name not in self.initializer.available_tools:
                    if self.verbose:
                        print(f"\n==> 🚫 Error: Tool '{tool_name}' is not available or not found.")
                    break
                
                # 执行工具命令
                executions = self.executor.execute_tool_command(tool_name, command)
                
                if self.verbose:
                    print(f"\n[Result]:")
                    formatted_result = make_json_serializable_truncated(executions, max_length=1000)
                    print(formatted_result)
                    print(f"[Time]: {time.time() - execution_start:.2f}s")
                
                # 添加到内存
                self.memory.add_action(step_count, tool_name, sub_goal, command, executions)
                
                # 验证上下文并决定是否继续
                if self.verbose:
                    print(f"\n==> 🤖 Step {step_count}: Context Verification")
                
                verification_start = time.time()
                
                verification = self.planner.verificate_context(question, image, query_analysis, self.memory)
                analysis, conclusion = self.planner.extract_conclusion(verification)
                
                if self.verbose:
                    print(f"\n[Analysis]: {analysis}")
                    print(f"[Conclusion]: {conclusion} {'🛑' if conclusion == 'CONTINUE' else '✅'}")
                    print(f"[Time]: {time.time() - verification_start:.2f}s")
                
                # 显示语义进度报告
                if self.verbose and hasattr(self.memory, 'generate_workflow_report'):
                    print(f"\n[Semantic Status]:")
                    print(self.memory.generate_workflow_report())
                
                # 检查是否应该停止
                if conclusion == 'STOP':
                    if self.verbose:
                        print(f"\n==> ✅ Context verification complete. Proceeding to final output.")
                    break
                
                step_count += 1
            
            # 生成最终输出
            if self.verbose:
                print(f"\n==> 🐙 Final Answer:")
            
            final_output = self._generate_final_output(question, image)
            
            if self.verbose:
                total_time = time.time() - start_time
                print(f"\n[Total Time]: {total_time:.2f}s")
                print(f"\n==> ✅ Query Solved!")
            
            return final_output
            
        except Exception as e:
            error_msg = f"Error during solving: {str(e)}"
            if self.verbose:
                print(f"\n==> ❌ {error_msg}")
            return error_msg

    def _setup_query_cache(self) -> str:
        """设置查询缓存目录"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_cache_dir = os.path.join(self.root_cache_dir, timestamp)
        os.makedirs(query_cache_dir, exist_ok=True)
        return query_cache_dir

    def _generate_final_output(self, question: str, image: str) -> str:
        """生成最终输出"""
        if "direct" in self.output_types:
            return self.planner.generate_direct_output(question, image, self.memory)
        elif "final" in self.output_types:
            return self.planner.generate_final_output(question, image, self.memory)
        else:
            return self.planner.generate_direct_output(question, image, self.memory)

    def get_semantic_status(self) -> Dict[str, Any]:
        """获取当前语义状态"""
        return {
            "semantic_registry": self.semantic_registry.get_completion_status(),
            "memory_progress": self.memory.get_workflow_progress() if hasattr(self.memory, 'get_workflow_progress') else {},
            "available_fragments": list(self.semantic_registry.fragments.keys()),
            "next_possible": self.semantic_registry.get_next_possible_types(),
            "executor_variables": list(self.executor.global_variables.keys())
        }

    def export_solution(self, output_dir: str = ".") -> Dict[str, str]:
        """导出完整解决方案"""
        results = {}
        
        # 导出语义片段
        if hasattr(self.memory, 'export_semantic_fragments'):
            fragments_dir = self.memory.export_semantic_fragments(output_dir)
            results["fragments_directory"] = fragments_dir
        
        # 导出完整解决方案
        complete_solution = self.semantic_registry.get_fragment(SemanticTypes.COMPLETE_SOLUTION)
        if complete_solution:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            solution_file = os.path.join(output_dir, f"complete_solution_{timestamp}.py")
            
            with open(solution_file, 'w', encoding='utf-8') as f:
                f.write(complete_solution.code)
            
            results["solution_file"] = solution_file
        
        # 导出语义状态报告
        status_file = os.path.join(output_dir, f"semantic_status_{timestamp}.json")
        with open(status_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(self.get_semantic_status(), f, indent=2, default=str)
        results["status_file"] = status_file
        
        return results

# 向后兼容：保持原有的构造函数
def construct_solver(
    llm_engine_name: str,
    enabled_tools: List[str] = ["all"],
    output_types: str = "final,direct",
    max_steps: int = 10,
    max_time: int = 300,
    max_tokens: int = 4000,
    root_cache_dir: str = "solver_cache",
    verbose: bool = False
) -> SemanticSolver:
    """构造语义感知求解器（保持向后兼容的接口）"""
    
    return SemanticSolver(
        llm_engine_name=llm_engine_name,
        enabled_tools=enabled_tools,
        output_types=output_types,
        max_steps=max_steps,
        max_time=max_time,
        max_tokens=max_tokens,
        root_cache_dir=root_cache_dir,
        verbose=verbose
    )

# 为了完全向后兼容，也可以保留旧的类名
class Solver(SemanticSolver):
    """向后兼容的求解器别名"""
    pass