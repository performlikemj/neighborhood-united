#!/usr/bin/env python
import sys
from sautai_agents.crew import SautaiAgentsCrew

# This main file is intended to be a way for your to run your
# crew locally, so refrain from adding necessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew and output the results.
    """
    # Run the crew
    results = SautaiAgentsCrew().crew().kickoff()

    # Display the results
    for task_name, task_output in results.items():
        print(f"\n=== Results for {task_name} ===")
        if isinstance(task_output, list):
            for item in task_output:
                print(f"- {item}")
        else:
            print(task_output)

if __name__ == "__main__":
    run()


# def train():
#     """
#     Train the crew for a given number of iterations.
#     """
#     inputs = {
#         "topic": "AI LLMs"
#     }
#     try:
#         SautaiAgentsCrew().crew().train(n_iterations=int(sys.argv[1]), inputs=inputs)

#     except Exception as e:
#         raise Exception(f"An error occurred while training the crew: {e}")

# def replay():
#     """
#     Replay the crew execution from a specific task.
#     """
#     try:
#         SautaiAgentsCrew().crew().replay(task_id=sys.argv[1])

#     except Exception as e:
#         raise Exception(f"An error occurred while replaying the crew: {e}")
