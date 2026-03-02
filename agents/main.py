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
from tool_scripts.simulator_tool import run_simulation

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
    
    # Create RTL with both a syntax error AND a logical bug
    test_file_path = "work/alu.sv"
    with open(test_file_path, "w") as f:
        f.write("module alu(input clk, input d, output reg q);\n")
        f.write("  always @(posedge clk) q = ~d \n") # BUG 1: blocking/syntax, BUG 2: logical (~d)
        f.write("endmodule\n")
        
    # Create a simple testbench to simulate the RTL
    tb_file_path = "work/tb_alu.sv"
    with open(tb_file_path, "w") as f:
        f.write("module tb_alu;\n")
        f.write("  reg clk, d; wire q;\n")
        f.write("  alu uut(.clk(clk), .d(d), .q(q));\n")
        f.write("  always #5 clk = ~clk;\n")
        f.write("  initial begin\n")
        f.write("    clk = 0; d = 0;\n")
        f.write("    #10 d = 1;\n")
        f.write("    #10;\n")
        f.write("    if (q !== 1) $display(\"SIMULATION FAILED: Expected q=1, got %b\", q);\n")
        f.write("    else $display(\"SIMULATION PASSED\");\n")
        f.write("    $finish;\n")
        f.write("  end\n")
        f.write("endmodule\n")

    # 3. Configure the LLM Client using the Anthropic extension
    model_client = AnthropicChatCompletionClient(
        model="claude-3-5-sonnet-20240620",
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )
    # 4. Define the Verification Agent (Combines Linting and Simulation)
    verification_system_message = """
    You are a Senior VLSI Design Verification Engineer.
    Your task is to fix syntax errors AND logical bugs in SystemVerilog/Verilog files.
    Rule 1: Always use non-blocking assignments (<=) in sequential logic blocks.
    
    You have access to three tools:
    1. `run_linter(rtl_file)`: Runs Verilator to check for syntax errors.
    2. `run_simulation(tb_file, rtl_file)`: Compiles and runs the testbench.
    3. `write_file(filepath, content)`: Overwrites the file with your corrected code.
    
    Process:
    1. Run the linter on the RTL file. If there are errors, fix them using `write_file` and re-lint.
    2. Once linting passes, run the simulation using `run_simulation(tb_file, rtl_file)`.
    3. Read the simulation logs. If it says "SIMULATION FAILED", analyze the logic bug, rewrite the RTL using `write_file`, and re-simulate.
    4. Once the simulation log outputs "SIMULATION PASSED", reply with exactly "TERMINATE".
    """

    # AssistantAgent now natively supports executing Python function tools!
    verification_agent = AssistantAgent(
        name="Verification_Agent",
        model_client=model_client,
        system_message=verification_system_message,
        tools=[run_linter, run_simulation, write_file], # Hand all tools to the agent
    )

    # 5. Define Termination Conditions
    # Increased max messages to 15 to allow time for both linting and simulating
    termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(15)

    # 6. Create a Team and Task
    team = RoundRobinGroupChat([verification_agent], termination_condition=termination)
    task = f"Please lint, simulate, and fix the RTL file at {test_file_path} using the testbench at {tb_file_path}."
    
    print(f"Starting AutoGen Chat. Target file: {test_file_path}\n")
    
    # Run the agentic loop and stream the output to the console!
    await Console(team.run_stream(task=task))

if __name__ == "__main__":
    # The new architecture relies on asyncio to run efficiently
    asyncio.run(main())