import os
import asyncio
from dotenv import load_dotenv

# 1. New imports for the updated AutoGen architecture
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.anthropic import AnthropicChatCompletionClient

# Import the tool you built previously
from tool_scripts.linter_tool import run_linter

# Load API Keys
load_dotenv()

# 2. Define a new tool for writing code
# In the new architecture, we explicitly give the agent a tool to write its fixes to disk.
def write_file(filepath: str, content: str) -> str:
    """Writes the corrected SystemVerilog content to the given filepath."""
    try:
        with open(filepath, "w") as f:
            f.write(content)
        return f"Success: Wrote corrected code to {filepath}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"

async def main():
    # Ensure our working directory exists and create a broken file
    os.makedirs("work", exist_ok=True)
    test_file_path = "work/alu.sv"
    with open(test_file_path, "w") as f:
        f.write("module alu(input clk, input d, output reg q);\n")
        f.write("  always @(posedge clk) q = d \n") # Broken: blocking assignment and missing semicolon
        f.write("endmodule\n")

    # 3. Configure the LLM Client using the Anthropic extension
    model_client = AnthropicChatCompletionClient(
        model="claude-3-5-sonnet-20240620",
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )

    # 4. Define the Linter Agent
    linter_system_message = """
    You are a Senior VLSI Design Verification Engineer.
    Your task is to fix standard rule violations and syntax errors in SystemVerilog/Verilog files.
    Rule 1: Always use non-blocking assignments (<=) in sequential logic blocks.
    
    You have access to two tools:
    1. `run_linter(rtl_file)`: Runs Verilator to check the code.
    2. `write_file(filepath, content)`: Overwrites the file with your corrected code.
    
    Process:
    1. Run the linter on the provided file to read the errors.
    2. Rewrite the buggy parts and save the file using the `write_file` tool.
    3. Run the linter again to verify your fix worked.
    4. Once the linter passes completely, reply with exactly "TERMINATE".
    """

    # AssistantAgent now natively supports executing Python function tools!
    linter_agent = AssistantAgent(
        name="Linter_Agent",
        model_client=model_client,
        system_message=linter_system_message,
        tools=[run_linter, write_file], # Hand the tools directly to the agent
    )

    # 5. Define Termination Conditions
    # Stop the loop if the agent says TERMINATE, or forcibly stop after 10 messages
    termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(10)

    # 6. Create a Team and Task
    team = RoundRobinGroupChat([linter_agent], termination_condition=termination)
    task = f"Please check, fix, and verify the file located at {test_file_path}."
    
    print(f"Starting AutoGen Chat. Target file: {test_file_path}\n")
    
    # Run the agentic loop and stream the output to the console!
    await Console(team.run_stream(task=task))

if __name__ == "__main__":
    # The new architecture relies on asyncio to run efficiently
    asyncio.run(main())