import json
import os
import re
from typing import Any, Dict, List, Tuple

from octotools.engine.factory import create_llm_engine
from octotools.models.formatters import MemoryVerification, NextStep, QueryAnalysis
from octotools.models.memory import Memory


class Planner:
    def __init__(self, llm_engine_name: str, toolbox_metadata: dict = None, available_tools: List = None, verbose: bool = False):
        self.llm_engine_name = llm_engine_name
        self.llm_engine = create_llm_engine(model_string=llm_engine_name, is_multimodal=False)
        self.toolbox_metadata = toolbox_metadata if toolbox_metadata is not None else {}
        self.available_tools = available_tools if available_tools is not None else []
        self.verbose = verbose
    def generate_base_response(self, question: str, image: str, max_tokens: str = 4000) -> str:
        self.base_response = self.llm_engine(question, max_tokens=max_tokens)
        return self.base_response

    def analyze_query(self, question: str, image: str) -> str:
        query_prompt = f"""
Task: Analyze the given query with accompanying inputs and determine the skills and tools needed to address it effectively.

Available tools: {self.available_tools}

Metadata for the tools: {self.toolbox_metadata}

Query: {question}

Instructions:
1. Carefully read and understand the query and any accompanying inputs.
2. Identify the main objectives or tasks within the query.
3. List the specific skills that would be necessary to address the query comprehensively.
4. Examine the available tools in the toolbox and determine which ones might relevant and useful for addressing the query. Make sure to consider the user metadata for each tool, including limitations and potential applications (if available).
5. Provide a brief explanation for each skill and tool you've identified, describing how it would contribute to answering the query.
6. If this query is about generating quantum algorithm code, note that this is a MULTI-STEP CODE GENERATION task
7. The tools will generate code FRAGMENTS that need to be ASSEMBLED into a complete script
8. Each tool produces part of the solution, not the complete answer

Your response should include:
1. A concise summary of the query's main points and objectives, as well as content in any accompanying inputs.
2. A list of required skills, with a brief explanation for each.
3. A list of relevant tools from the toolbox, with a brief explanation of how each tool would be utilized and its potential limitations.
4. Any additional considerations that might be important for addressing the query effectively.

Please present your analysis in a clear, structured format.
"""

        self.query_analysis = self.llm_engine(query_prompt, response_format=QueryAnalysis)

        return str(self.query_analysis).strip()

    def extract_context_subgoal_and_tool(self, response: Any) -> Tuple[str, str, str]:

        def normalize_tool_name(tool_name: str) -> str:
            # Normalize the tool name to match the available tools
            for tool in self.available_tools:
                if tool.lower() in tool_name.lower():
                    return tool
            return "No matched tool given: " + tool_name

        try:
            if isinstance(response, str):
                # Attempt to parse the response as JSON
                try:
                    response_dict = json.loads(response)
                    response = NextStep(**response_dict)
                except Exception as e:
                    print(f"Failed to parse response as JSON: {str(e)}")
            if isinstance(response, NextStep):
                print("arielg 1")
                context = response.context.strip()
                sub_goal = response.sub_goal.strip()
                tool_name = response.tool_name.strip()
            else:
                print("arielg 2")
                text = response.replace("**", "")

                # Pattern to match the exact format
                pattern = r"Context:\s*(.*?)Sub-Goal:\s*(.*?)Tool Name:\s*(.*?)(?=\n\n|\Z)"

                # Find all matches
                matches = re.findall(pattern, text, re.DOTALL)

                # Return the last match (most recent/relevant)
                context, sub_goal, tool_name = matches[-1]
                context = context.strip()
                sub_goal = sub_goal.strip()
            tool_name = normalize_tool_name(tool_name)
        except Exception as e:
            print(f"Error extracting context, sub-goal, and tool name: {str(e)}")
            return None, None, None

        return context, sub_goal, tool_name

    def generate_next_step(self, question: str, image: str, query_analysis: str, memory: Memory, step_count: int, max_step_count: int) -> Any:
        prompt_generate_next_step = f"""







IMPORTANT - For code generation tasks:
- These tools generate CODE FRAGMENTS, not complete solutions
- Each tool contributes ONE PART of the final Python script
- The goal is to collect all necessary code pieces
- A final assembly step may be needed



        


        
Task: Determine the next step for a multi-component solution. Determine the optimal next step to address the given query based on the provided analysis, available tools, and previous steps taken.

Context:
Query: {question}
Query Analysis: {query_analysis}

Available Tools:
{self.available_tools}

Tool Metadata:
{self.toolbox_metadata}

Previous Steps and Their Results:
{memory.get_actions()}

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

3. Select ONE tool best suited for the next step, keeping in mind the limited number of remaining steps.

4. Formulate a specific, achievable sub-goal for the selected tool that maximizes progress towards answering the query.

5. If this is a code generation task, track what code fragments have been collected

6. Determine what code fragment is needed next

7. Plan for final code assembly when all fragments are ready

Response Format:
Your response MUST follow this structure:
1. Justification: Explain your choice in detail.
2. Context, Sub-Goal, and Tool: Present the context, sub-goal, and the selected tool ONCE with the following format:


Context: <Include specific data from previous steps AND mention this is part of code assembly>
Sub-Goal: <What code fragment or assembly step is needed>
Tool Name: <tool_name>


Where:
- <context> MUST include ALL necessary information for the tool to function, structured as follows:
  * Relevant data from previous steps
  * File names or paths created or used in previous steps (list EACH ONE individually)
  * Variable names and their values from previous steps' results
  * Any other context-specific information required by the tool
- <sub_goal> is a specific, achievable objective for the tool, based on its metadata and previous outcomes.
It MUST contain any involved data, file names, and variables from Previous Steps and Their Results that the tool can act upon.
- <tool_name> MUST be the exact name of a tool from the available tools list.

Rules:
- Select only ONE tool for this step.
- The sub-goal MUST directly address the query and be achievable by the selected tool.
- The Context section MUST include ALL necessary information for the tool to function, including ALL relevant file paths, data, and variables from previous steps.
- The tool name MUST exactly match one from the available tools list: {self.available_tools}.
- Avoid redundancy by considering previous steps and building on prior results.
- Your response MUST conclude with the Context, Sub-Goal, and Tool Name sections IN THIS ORDER, presented ONLY ONCE.
- Include NO content after these three sections.

Example (do not copy, use only as reference):
Justification: [Your detailed explanation here]
Context: Previous detection results: [list of objects]
Sub-Goal: Detect and count the number of specific objects in the image "example/image.jpg"
Tool Name: Object_Detector_Tool

Remember: Your response MUST end with the Context, Sub-Goal, and Tool Name sections, with NO additional content afterwards.
"""
        
        next_step = self.llm_engine(prompt_generate_next_step, response_format=NextStep)
        return next_step

    def verificate_context(self, question: str, image: str, query_analysis: str, memory: Memory) -> Any:
        prompt_memory_verification = f"""
Task: Thoroughly evaluate the completeness and accuracy of the memory for fulfilling the given query, considering the potential need for additional tool usage.

Context:
Query: {question}
Available Tools: {self.available_tools}
Toolbox Metadata: {self.toolbox_metadata}
Initial Analysis: {query_analysis}
Memory (tools used and results): {memory.get_actions()}

Detailed Instructions:
1. Carefully analyze the query, initial analysis:
   - Identify the main objectives of the query.
   - Note any specific requirements or constraints mentioned.

2. Review the available tools and their metadata:
   - Understand the capabilities and limitations and best practices of each tool.
   - Consider how each tool might be applicable to the query.

3. Examine the memory content in detail:
   - Review each tool used and its execution results.
   - Assess how well each tool's output contributes to answering the query.

4. Critical Evaluation (address each point explicitly):
   a) Completeness: Does the memory fully address all aspects of the query?
      - Identify any parts of the query that remain unanswered.

   b) Unused Tools: Are there any unused tools that could provide additional relevant information?
      - Specify which unused tools might be helpful and why.

   c) Inconsistencies: Are there any contradictions or conflicts in the information provided?
      - If yes, explain the inconsistencies and suggest how they might be resolved.

   d) Verification Needs: Is there any information that requires further verification due to tool limitations?
      - Identify specific pieces of information that need verification and explain why.

   e) Ambiguities: Are there any unclear or ambiguous results that could be clarified by using another tool?
      - Point out specific ambiguities and suggest which tools could help clarify them.
    
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
    - Individual code fragments are progress, not completion
      
6. Final Determination:
   Based on your thorough analysis, decide if the memory is complete and accurate enough to generate the final output, or if additional tool usage is necessary.

Response Format:

If the memory is complete, accurate, AND verified:
Explanation:
<Provide a detailed explanation of why the memory is sufficient. Reference specific information from the memory and explain its relevance to each aspect of the task. Address how each main point of the query has been satisfied.>

Conclusion: STOP

If the memory is incomplete, insufficient, or requires further verification:
Explanation:
<Explain in detail why the memory is incomplete. Identify specific information gaps or unaddressed aspects of the query. Suggest which additional tools could be used, how they might contribute, and why their input is necessary for a comprehensive response.>

Conclusion: CONTINUE

IMPORTANT: Your response MUST end with either 'Conclusion: STOP' or 'Conclusion: CONTINUE' and nothing else. Ensure your explanation thoroughly justifies this conclusion.
"""

        stop_verification = self.llm_engine(prompt_memory_verification, response_format=MemoryVerification)

        return stop_verification

    def extract_conclusion(self, response: Any) -> tuple:
        if isinstance(response, str):
            # Attempt to parse the response as JSON
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
            # if match:
            #     conclusion = match.group(1).upper()
            #     if conclusion in ['STOP', 'CONTINUE']:
            #         return conclusion
            if matches:
                conclusion = matches[-1].group(1).upper()
                if conclusion in ['STOP', 'CONTINUE']:
                    return analysis, conclusion

            # If no valid conclusion found, search for STOP or CONTINUE anywhere in the text
            if 'stop' in response.lower():
                return analysis, 'STOP'
            elif 'continue' in response.lower():
                return analysis, 'CONTINUE'
            else:
                print("No valid conclusion (STOP or CONTINUE) found in the response. Continuing...")
                return analysis, 'CONTINUE'

    def generate_final_output(self, question: str, image: str, memory: Memory) -> str:
        prompt_generate_final_output = f"""
Task: Generate the final output based on the query and tools used in the process.

Context:
Query: {question}
Actions Taken:
{memory.get_actions()}

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
        prompt_generate_final_output = f"""
Context:
Query: {question}
Initial Analysis:
{self.query_analysis}
Actions Taken:
{memory.get_actions()}

Please generate the completed python code to answer the user query. Take care of the format and complteness about the answer code. Conclude with a precise and direct answer to the query.

Answer:
"""

        final_output = self.llm_engine(prompt_generate_final_output)

        return final_output