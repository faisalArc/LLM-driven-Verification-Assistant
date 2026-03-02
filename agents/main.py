import os
import asyncio
from dotenv import load_dotenv

# AutoGen Architecture Imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.anthropic import AnthropicChatCompletionClient

# Import your custom tools
from linter_tool import run_linter
from simulator_tool import run_simulation
from vcd_parser_tool import parse_vcd_to_text

# ==========================================
# MODULE 1: File I/O & Tool Wrappers
# ==========================================
def write_file(filepath: str, content: str) -> str:
    """Allows agents to write code or reports to the disk."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        return f"Success: Wrote file to {filepath}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def read_file(filepath: str) -> str:
    """Allows agents to read existing files from the disk."""
    try:
        with open(filepath, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

# ==========================================
# MODULE 2: Deterministic Routing Graph
# ==========================================
def state_transition_graph(messages) -> str:
    """
    StateFlow Router: Bypasses the LLM to enforce strict transition logic.
    Solves the Chain of Thought problem by hardcoding the verification pipeline.
    """
    if not messages:   # attribute of the state_trasition_graph function
        return "Orchestrator_Agent"
        
    last_msg = messages[-1]
    sender = last_msg.source
    
    # Safely extract message text
    content = ""
    if hasattr(last_msg, "content") and isinstance(last_msg.content, str):
        content = last_msg.content.lower()
        
    # --- The State Machine Edges ---
    if sender == "user":
        return "Orchestrator_Agent"
        
    elif sender == "Orchestrator_Agent":
        return "Reference_Model_Agent"
        
    elif sender == "Reference_Model_Agent":
        return "Linter_Agent"
        
    elif sender == "Linter_Agent":
        # Check if the Linter succeeded. If yes, move to Simulator.
        if "success" in content or "no linting errors" in content:
            return "Simulation_Agent"
        # If the linter found errors, loop back to the Linter Agent so it can fix them
        return "Linter_Agent"
        
    elif sender == "Simulation_Agent":
        # If compilation fails, kick the testbench back to the Linter to fix syntax
        if "compilation failed" in content:
            return "Linter_Agent"
        # If simulation runs successfully, move to Debug phase
        return "Debug_Agent"
        
    elif sender == "Debug_Agent":
        # Debug phase is over; send the report back to the Orchestrator 
        # to generate a new Verification Plan and Testbench
        return "Orchestrator_Agent"
        
    # Fallback safety net
    return "Orchestrator_Agent"

# ==========================================
# MODULE 3: Coverage-Driven Agents
# ==========================================
def create_orchestrator(model_client) -> AssistantAgent:
    system_message = """
    You are the Lead Verification Orchestrator. 
    Your goal is Coverage-Driven Verification (CDV).
    
    Process:
    1. Read the initial Design Specification.
    2. Write a SystemVerilog Testbench using `write_file` (save as 'work/tb_alu.sv'). 
    3. DO NOT rewrite the RTL. Treat the RTL ('work/alu.sv') as a fixed Device Under Test.
    4. When the Debug Agent returns a failure report, write an updated Testbench to fix the test bugs or hit new edge cases.
    5. Once the Debug Agent confirms the test passes and coverage is hit, reply with exactly "TERMINATE".
    """
    return AssistantAgent("Orchestrator_Agent", model_client, system_message, tools=[write_file, read_file])

def create_ref_model_agent(model_client) -> AssistantAgent:
    system_message = """
    You are the Reference Model Agent.
    1. Read the Design Spec provided by the Orchestrator.
    2. Use `write_file` to create a Golden Python Model at 'work/ref_model.py'.
    3. Conclude your message with "Reference Model Generated." Do not output TERMINATE.
    """
    return AssistantAgent("Reference_Model_Agent", model_client, system_message, tools=[write_file])

def create_linter_agent(model_client) -> AssistantAgent:
    system_message = """
    You are the Linter Agent. Your ONLY job is static analysis.
    1. Run `run_linter(rtl_file)` on BOTH the RTL and Testbench files.
    2. If there are syntax errors, use `write_file` to fix them.
    3. Once there are no errors, output the exact phrase: "SUCCESS: No linting errors."
    """
    return AssistantAgent("Linter_Agent", model_client, system_message, tools=[run_linter, write_file])

def create_simulation_agent(model_client) -> AssistantAgent:
    system_message = """
    You are the Simulation Agent. Your ONLY job is to extract execution data.
    1. Run `run_simulation(tb_file, rtl_file)`.
    2. If compilation fails, output "Compilation Failed".
    3. If simulation succeeds, run `parse_vcd_to_text(vcd_file)` to extract the truth table.
    4. Output the compilation logs AND the parsed VCD text.
    Do not debug or rewrite code.
    """
    return AssistantAgent("Simulation_Agent", model_client, system_message, tools=[run_simulation, parse_vcd_to_text])

def create_debug_agent(model_client) -> AssistantAgent:
    system_message = """
    You are the Debug Agent. Your ONLY job is analysis.
    1. Compare the VCD table provided by the Simulator against the Reference Model.
    2. Write a markdown report using `write_file` (save as 'work/debug_report.md').
    3. Conclude your message with "Debug Report Generated. Orchestrator, please review."
    Do not output TERMINATE.
    """
    return AssistantAgent("Debug_Agent", model_client, system_message, tools=[write_file, read_file])

# ==========================================
# MODULE 4: Orchestration & Execution
# ==========================================
async def main():
    load_dotenv()
    os.makedirs("work", exist_ok=True)
    
    # Dummy RTL (The Device Under Test)
    test_file_path = "../work/alu.sv"
    with open(test_file_path, "w") as f:
        f.write("module alu(input clk, input d, output reg q);\n")
        f.write("  always @(posedge clk) q <= d;\n") 
        f.write("endmodule\n")

    initial_spec = "Design a simple ALU that acts as a D-Flip Flop (q <= d on posedge clk)."
    
    # Setup LLM
    model_client = AnthropicChatCompletionClient(
        model="claude-3-5-sonnet-20240620",
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )

    # Initialize Team
    orchestrator = create_orchestrator(model_client)
    ref_agent = create_ref_model_agent(model_client)
    linter_agent = create_linter_agent(model_client)
    sim_agent = create_simulation_agent(model_client)
    debug_agent = create_debug_agent(model_client)

    # Stop on success or after 30 interactions 
    termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(30)

    # Instantiate the Strict State Machine
    team = SelectorGroupChat(
        participants=[orchestrator, ref_agent, linter_agent, sim_agent, debug_agent],
        model_client=model_client,
        termination_condition=termination,
        selector_func=state_transition_graph, # Overrides the LLM with deterministic routing!
        allow_repeated_speaker=True # Allows the Linter to loop back to itself if needed
    )
    
    human_task = f"""
    HUMAN LEAD INPUT:
    Here is the Design Spec: {initial_spec}
    The Device Under Test (RTL) is located at 'work/alu.sv'.
    Orchestrator_Agent, generate the Verification Plan and Testbench!
    """
    
    print("==================================================")
    print("Starting Deterministic StateFlow Verification Loop")
    print("==================================================\n")
    await Console(team.run_stream(task=human_task))

if __name__ == "__main__":
    asyncio.run(main())