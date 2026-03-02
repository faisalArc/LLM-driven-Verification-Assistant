import os
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.anthropic import AnthropicChatCompletionClient

def write_ref_model(filepath: str, content: str) -> str:
    """Writes the generated Python reference model to the given filepath."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        return f"Success: Wrote python reference model to {filepath}"
    except Exception as e:
        return f"Error writing reference model to file: {str(e)}"

def create_reference_model_agent(model_client: AnthropicChatCompletionClient) -> AssistantAgent:
    """
    Initializes and returns the Reference Model Agent.
    This agent is responsible for translating human specifications into a Golden Python Model.
    """
    ref_model_system_message = """
    You are a Senior VLSI Verification Architect.
    Your specific task is to write a high-level "Golden" Reference Model in Python based on the provided hardware design specifications.
    This reference model must simulate the functional behavior of the intended RTL design (e.g., computing the expected output for a given input).
    
    Process:
    1. Read the design specification provided by the Orchestrator.
    2. Write a clean, well-documented Python script that models this behavior. The script should be able to take inputs (e.g., via arguments or reading a file) and produce expected outputs.
    3. Use the `write_ref_model(filepath, content)` tool to save your Python script to the disk (save it as 'work/ref_model.py').
    4. Once the file is successfully written, reply with exactly "TERMINATE".
    """

    agent = AssistantAgent(
        name="Reference_Model_Agent",
        model_client=model_client,
        system_message=ref_model_system_message,
        tools=[write_ref_model], 
    )
    
    return agent

# ==========================================
# Example usage / Testing the agent locally
# ==========================================
if __name__ == "__main__":
    import asyncio
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
    from autogen_agentchat.ui import Console
    from dotenv import load_dotenv

    load_dotenv()
    
    async def test_ref_agent():
        client = AnthropicChatCompletionClient(
            model="claude-3-5-sonnet-20240620",
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
        
        ref_agent = create_reference_model_agent(client)
        termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(5)
        team = RoundRobinGroupChat([ref_agent], termination_condition=termination)
        
        # Give it a mock specification to model
        spec = "Design a simple ALU that takes a 1-bit 'clk', 1-bit input 'd', and outputs a 1-bit 'q'. It acts as a D-Flip Flop (q <= d on the posedge of clk)."
        task = f"Create a python reference model for the following spec: {spec}"
        
        print("Starting Reference Model Agent Test...\n")
        await Console(team.run_stream(task=task))

    asyncio.run(test_ref_agent())