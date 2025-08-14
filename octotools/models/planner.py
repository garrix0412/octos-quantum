# octotools/models/planner.py
import json
import os
import re
from typing import Any, Dict, List, Tuple

from octotools.engine.factory import create_llm_engine
from octotools.models.formatters import MemoryVerification, NextStep, QueryAnalysis
from octotools.models.memory import Memory
from octotools.models.semantic_types import SemanticTypes
from octotools.models.semantic_registry import SemanticRegistry

class Planner:
    """升级版规划器 - 语义感知 + 向后兼容"""
    
    def __init__(self, llm_engine_name: str, toolbox_metadata: dict = None, 
                 available_tools: List = None, verbose: bool = False):
        self.llm_engine_name = llm_engine_name
        self.llm_engine = create_llm_engine(model_string=llm_engine_name, is_multimodal=False)
        self.toolbox_metadata = toolbox_metadata if toolbox_metadata is not None else {}
        self.available_tools = available_tools if available_tools is not None else []
        self.verbose = verbose
        
        # 新增：语义化组件
        self.semantic_registry = SemanticRegistry()
        
    def set_semantic_registry(self, semantic_registry: SemanticRegistry):
        """设置语义注册表（由执行器传入）"""
        self.semantic_registry = semantic_registry

    def generate_base_response(self, question: str, image: str, max_tokens: str = 4000) -> str:
        """生成基础响应（保持原接口）"""
        self.base_response = self.llm_engine(question, max_tokens=max_tokens)
        return self.base_response

    def analyze_query(self, question: str, image: str) -> str:
        """分析查询（升级为语义感知）"""
        query_prompt = f"""
Task: Analyze the query and determine the required skills, tools, and semantic workflow.

Available tools: {self.available_tools}
Tool metadata: {self.toolbox_metadata}
Query: {question}

Semantic Framework Context:
- This is a SEMANTIC CODE GENERATION system
- Tools generate executable code fragments with specific semantic types
- Each semantic type has clear dependencies that must be satisfied
- The goal is to assemble a complete executable quantum algorithm

Semantic Types and Dependencies:
{SemanticTypes.DEPENDENCIES}

Tool to Semantic Type Mapping:
{SemanticTypes.TOOL_SEMANTIC_MAPPING}

Instructions:
1. Identify the main objectives and determine if this is a code generation task
2. If it's a quantum algorithm task, identify the required semantic workflow
3. List the skills needed and tools that can address the query
4. Consider the semantic dependency order for multi-step code generation
5. Note that tools generate CODE FRAGMENTS that need to be ASSEMBLED

Your response should include:
1. A concise summary of the query's requirements
2. Required skills with explanations
3. Relevant tools and their semantic roles
4. Additional considerations for the code generation workflow

Present your analysis in a clear, structured format.
"""

        self.query_analysis = self.llm_engine(query_prompt, response_format=QueryAnalysis)
        return str(self.query_analysis).strip()

    def extract_context_subgoal_and_tool(self, response: Any) -> Tuple[str, str, str]:
        """提取上下文、子目标和工具（保持原逻辑）"""
        def normalize_tool_name(tool_name: str) -> str:
            for tool in self.available_tools:
                if tool.lower() in tool_name.lower():
                    return tool
            return "No matched tool given: " + tool_name

        try:
            if isinstance(response, str):
                try:
                    response_dict = json.loads(response)
                    response = NextStep(**response_dict)
                except Exception as e:
                    print(f"Failed to parse response as JSON: {str(e)}")
                    
            if isinstance(response, NextStep):
                context = response.context.strip()
                sub_goal = response.sub_goal.strip()
                tool_name = response.tool_name.strip()
            else:
                text = response.replace("**", "")
                pattern = r"Context:\s*(.*?)Sub-Goal:\s*(.*?)Tool Name:\s*(.*?)(?=\n\n|\Z)"
                matches = re.findall(pattern, text, re.DOTALL)
                context, sub_goal, tool_name = matches[-1]
                context = context.strip()
                sub_goal = sub_goal.strip()
                
            tool_name = normalize_tool_name(tool_name)
            
        except Exception as e:
            print(f"Error extracting context, sub-goal, and tool name: {str(e)}")
            return None, None, None

        return context, sub_goal, tool_name

    def generate_next_step(self, question: str, image: str, query_analysis: str, 
                          memory: Memory, step_count: int, max_step_count: int) -> Any:
        """生成下一步（升级为语义感知）"""
        
        # 获取语义状态（如果可用）
        semantic_info = ""
        if hasattr(self, 'semantic_registry') and self.semantic_registry:
            semantic_status = self.semantic_registry.get_completion_status()
            available_types = list(self.semantic_registry.fragments.keys())
            next_possible = self.semantic_registry.get_next_possible_types()
            
            semantic_info = f"""
Semantic State:
- Completed semantic types: {available_types}
- Completion status: {semantic_status}
- Next possible types: {next_possible}

Semantic Dependencies:
{SemanticTypes.DEPENDENCIES}

Tool Semantic Mapping:
{SemanticTypes.TOOL_SEMANTIC_MAPPING}
"""
        
        prompt_generate_next_step = f"""
IMPORTANT - For code generation tasks:
- These tools generate CODE FRAGMENTS, not complete solutions
- Each tool contributes ONE PART of the final Python script
- The goal is to collect all necessary code pieces
- A final assembly step may be needed

{semantic_info}

Task: Determine the optimal next step to address the given query based on the provided analysis, available tools, and previous steps taken.

Context:
Query: {question}
Query Analysis: {query_analysis}

Available Tools: {self.available_tools}
Tool Metadata: {self.toolbox_metadata}

Previous Steps and Their Results: {memory.get_actions()}

Current Step: {step_count} in {max_step_count} steps
Remaining Steps: {max_step_count - step_count}

Instructions:
1. Analyze the context thoroughly, including the query, its analysis, available tools and their metadata, and previous steps taken.

2. Determine the most appropriate next step by considering:
   - Key objectives from the query analysis
   - Capabilities of available tools
   - Logical progression of problem-solving
   - Outcomes from previous steps
   - Current step count and remaining steps
   - Semantic dependencies (if applicable)

3. Select ONE tool best suited for the next step, keeping in mind the limited number of remaining steps.

4. Formulate a specific, achievable sub-goal for the selected tool that maximizes progress towards answering the query.

5. If this is a code generation task, track what code fragments have been collected and determine what code fragment is needed next

6. Plan for final code assembly when all fragments are ready

Response Format:
Your response MUST follow this structure:
1. Justification: Explain your choice in detail.
2. Context, Sub-Goal, and Tool: Present the context, sub-goal, and the selected tool ONCE with the following format:

Context: <Include specific data from previous steps AND mention this is part of code assembly>
Sub-Goal: <What code fragment or assembly step is needed>
Tool Name: <tool_name>

Where:
- <context> MUST include ALL necessary information for the tool to function
- <sub_goal> is a specific, achievable objective for the tool
- <tool_name> MUST be the exact name of a tool from the available tools list.

Rules:
- Select only ONE tool for this step.
- The sub-goal MUST directly address the query and be achievable by the selected tool.
- The tool name MUST exactly match one from the available tools list: {self.available_tools}.
- Consider semantic dependencies if this is a code generation workflow
- Your response MUST conclude with the Context, Sub-Goal, and Tool Name sections IN THIS ORDER.
"""
        
        next_step = self.llm_engine(prompt_generate_next_step, response_format=NextStep)
        return next_step

    def verificate_context(self, question: str, image: str, query_analysis: str, memory: Memory) -> Any:
        """验证上下文（升级为语义感知）"""
        
        # 获取语义状态（如果可用）
        semantic_verification = ""
        if hasattr(self, 'semantic_registry') and self.semantic_registry:
            semantic_status = self.semantic_registry.get_completion_status()
            available_types = list(self.semantic_registry.fragments.keys())
            required_for_complete = [
                SemanticTypes.SPEC, SemanticTypes.HAMILTONIAN, SemanticTypes.ANSATZ,
                SemanticTypes.OPTIMIZER, SemanticTypes.VQE_EXECUTION, SemanticTypes.COMPLETE_SOLUTION
            ]
            missing_types = set(required_for_complete) - set(available_types)
            
            semantic_verification = f"""
Semantic Workflow Analysis:
- Available semantic fragments: {available_types}
- Required for complete solution: {required_for_complete}
- Missing semantic types: {list(missing_types)}
- Completion status: {semantic_status}

Semantic Completeness Check:
- Individual fragments are progress, NOT completion
- Must have complete_solution semantic type for true completion
- The task is ONLY complete when a full, executable Python script is generated
"""
        
        prompt_memory_verification = f"""
Task: Thoroughly evaluate the completeness and accuracy of the memory for fulfilling the given query, considering the potential need for additional tool usage.

Context:
Query: {question}
Available Tools: {self.available_tools}
Toolbox Metadata: {self.toolbox_metadata}
Initial Analysis: {query_analysis}
Memory (tools used and results): {memory.get_actions()}

{semantic_verification}

Detailed Instructions:
1. Carefully analyze the query, initial analysis:
   - Identify the main objectives of the query.
   - Note any specific requirements or constraints mentioned.

2. Review the available tools and their metadata:
   - Understand the capabilities and limitations of each tool.
   - Consider how each tool might be applicable to the query.

3. Examine the memory content in detail:
   - Review each tool used and its execution results.
   - Assess how well each tool's output contributes to answering the query.

4. Critical Evaluation (address each point explicitly):
   a) Completeness: Does the memory fully address all aspects of the query?
   b) Unused Tools: Are there any unused tools that could provide additional relevant information?
   c) Inconsistencies: Are there any contradictions or conflicts in the information provided?
   d) Verification Needs: Is there any information that requires further verification?
   e) Ambiguities: Are there any unclear or ambiguous results that could be clarified?
    
5. Special Consideration for Code Generation Tasks:
    - For queries asking to generate quantum algorithm code, check:
        1. Have all necessary code fragments been generated?
        2. Spec/Problem definition ✓
        3. Hamiltonian code ✓  
        4. Ansatz code ✓
        5. Optimizer configuration ✓
        6. VQE execution code ✓
        7. Final code assembly ✓
    - The task is ONLY complete when a full, executable Python script is generated
      
6. Final Determination:
   Based on your thorough analysis, decide if the memory is complete and accurate enough to generate the final output, or if additional tool usage is necessary.

Response Format:

If the memory is complete, accurate, AND verified:
Explanation:
<Provide a detailed explanation of why the memory is sufficient, covering all aspects>

Conclusion: STOP

If the memory is incomplete, insufficient, or requires further verification:
Explanation:
<Explain in detail why the memory is incomplete and what additional steps are needed>

Conclusion: CONTINUE

IMPORTANT: Your response MUST end with either 'Conclusion: STOP' or 'Conclusion: CONTINUE'
"""

        stop_verification = self.llm_engine(prompt_memory_verification, response_format=MemoryVerification)
        return stop_verification

    def extract_conclusion(self, response: Any) -> tuple:
        """提取结论（保持原逻辑）"""
        if isinstance(response, str):
            try:
                response_dict = json.loads(response)
                response = MemoryVerification(**response_dict)
            except Exception as e:
                print(f"Failed to parse response as JSON: {str(e)}")
                
        if isinstance(response, MemoryVerification):
            analysis = response.analysis
            stop_signal = response.stop_signal
            if stop_signal:
                return analysis, 'STOP'
            else:
                return analysis, 'CONTINUE'
        else:
            analysis = response
            pattern = r'conclusion\**:?\s*\**\s*(\w+)'
            matches = list(re.finditer(pattern, response, re.IGNORECASE | re.DOTALL))
            
            if matches:
                conclusion = matches[-1].group(1).upper()
                if conclusion in ['STOP', 'CONTINUE']:
                    return analysis, conclusion

            # 后备检查
            if 'stop' in response.lower():
                return analysis, 'STOP'
            elif 'continue' in response.lower():
                return analysis, 'CONTINUE'
            else:
                print("No valid conclusion found. Continuing...")
                return analysis, 'CONTINUE'

    def generate_final_output(self, question: str, image: str, memory: Memory) -> str:
        """生成最终输出（升级版本）"""
        
        # 获取语义信息（如果可用）
        semantic_summary = ""
        if hasattr(self, 'semantic_registry') and self.semantic_registry:
            all_fragments = list(self.semantic_registry.fragments.values())
            if all_fragments:
                fragment_info = [f"- {f.semantic_type}: {f.tool_source}" for f in all_fragments]
                semantic_summary = f"""
Semantic Components Generated:
{chr(10).join(fragment_info)}
"""
        
        prompt_generate_final_output = f"""
Task: Generate the final output based on the query and tools used in the process.

Context:
Query: {question}
Actions Taken: {memory.get_actions()}
{semantic_summary}

Instructions:
1. Review the query and all actions taken during the process.
2. Consider the results obtained from each tool execution.
3. Incorporate the relevant information from the memory to generate the step-by-step final output.
4. The final output should be consistent and coherent using the results from the tools.

Output Structure:
Your response should be well-organized and include the following sections:

1. Summary:
   - Provide a brief overview of the query and the main findings.

2. Detailed Analysis:
   - Break down the process of answering the query step-by-step.
   - For each step, mention the tool used, its purpose, and the key results obtained.
   - Explain how each step contributed to addressing the query.

3. Key Findings:
   - List the most important discoveries or insights gained from the analysis.
   - Highlight any unexpected or particularly interesting results.

4. Answer to the Query:
   - Directly address the original question with a clear and concise answer.
   - If the query has multiple parts, ensure each part is answered separately.

5. Additional Insights (if applicable):
   - Provide any relevant information or insights that go beyond the direct answer to the query.
   - Discuss any limitations or areas of uncertainty in the analysis.

6. Conclusion:
   - Summarize the main points and reinforce the answer to the query.
   - If appropriate, suggest potential next steps or areas for further investigation.
"""

        final_output = self.llm_engine(prompt_generate_final_output)
        return final_output

    def generate_direct_output(self, question: str, image: str, memory: Memory) -> str:
        """生成直接输出（升级版本）"""
        
        # 获取语义信息（如果可用）
        complete_solution_info = ""
        if hasattr(self, 'semantic_registry') and self.semantic_registry:
            complete_solution = self.semantic_registry.get_fragment(SemanticTypes.COMPLETE_SOLUTION)
            all_fragments = list(self.semantic_registry.fragments.values())
            complete_solution_info = f"""
Semantic Fragments: {len(all_fragments)} fragments generated
Complete Solution Available: {complete_solution is not None}
"""
        
        prompt_generate_direct_output = f"""
Context:
Query: {question}
Initial Analysis: {self.query_analysis if hasattr(self, 'query_analysis') else 'Not available'}
{complete_solution_info}
Actions Taken: {memory.get_actions()}

Please generate the completed python code to answer the user query. Take care of the format and completeness about the answer code. Conclude with a precise and direct answer to the query.

Answer:
"""

        final_output = self.llm_engine(prompt_generate_direct_output)
        return final_output