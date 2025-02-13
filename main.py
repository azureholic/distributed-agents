from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import CodeInterpreterTool
import os
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
aifoundry_project_connectionstring = os.getenv("AIFOUNDRY_PROJECT_CONNECTIONSTRING")

token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

az_model_client = AzureOpenAIChatCompletionClient(
    azure_deployment="gpt-4o-mini",
    api_version="2024-05-01-preview",
    model = "gpt-4o-mini",
    azure_endpoint=azure_openai_endpoint,
    azure_ad_token_provider=token_provider,  # Optional if you choose key-based authentication.
    # api_key="sk-...", # For key-based authentication.
)

project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str=aifoundry_project_connectionstring,
)

async def save_blog_agent(blog_content: str) -> str:

    print("This is Code Interpreter for Azure AI Agent Service .......")


    code_interpreter = CodeInterpreterTool()
        
    agent = project_client.agents.create_agent(
            model="gpt-4o-mini",
            name="save-blog-agent",
            instructions="You are helpful agent",
            tools=code_interpreter.definitions,
            # tool_resources=code_interpreter.resources,
    )

    thread = project_client.agents.create_thread()

    message = project_client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content="""
        
                    You are my Python programming assistant. Generate code,save """+ blog_content +
                    
                """    
                    and execute it according to the following requirements

                    1. Save blog content to blog-{YYMMDDHHMMSS}.md

                    2. give me the download this file link
                """,
    )
    # create and execute a run
    run = project_client.agents.create_and_process_run(thread_id=thread.id, assistant_id=agent.id)
    print(f"Run finished with status: {run.status}")

    if run.status == "failed":
            # Check if you got "Rate limit is exceeded.", then you want to get more quota
        print(f"Run failed: {run.last_error}")

        # # delete the original file from the agent to free up space (note: this does not delete your version of the file)
        # project_client.agents.delete_file(file.id)
        # print("Deleted file")

        # print the messages from the agent
    
    
    messages = project_client.agents.list_messages(thread_id=thread.id)
    print(f"Messages: {messages}")

        # get the most recent message from the assistant
       
    last_msg = messages.get_last_text_message_by_role("assistant")
    if last_msg:
        print(f"Last Message: {last_msg.text.value}")

        # print(f"File: {messages.file_path_annotations}")


    for file_path_annotation in messages.file_path_annotations:

        file_name = os.path.basename(file_path_annotation.text)

        project_client.agents.save_file(file_id=file_path_annotation.file_path.file_id, file_name=file_name,target_dir="./blog")
        

    project_client.agents.delete_agent(agent.id)
    print("Deleted agent")


        # project_client.close()


    return "Saved"


    
    
save_blog_content_agent = AssistantAgent(
    name="save_blog_content_agent",
    model_client=az_model_client,
    tools=[save_blog_agent],
    system_message="""
        Save blog content in markdown format. 
        Respond with 'Saved' 
        A give me a link to the file to download
    """
)

write_agent = AssistantAgent(
    name="write_agent",
    model_client=az_model_client,
    system_message="""
        You are a blog writer, please help me write a blog."
    """
)

text_termination = TextMentionTermination("Saved")
# Define a termination condition that stops the task after 5 messages.
max_message_termination = MaxMessageTermination(10)
# Combine the termination conditions using the `|`` operator so that the
# task stops when either condition is met.
termination = text_termination | max_message_termination


reflection_team = RoundRobinGroupChat([write_agent,save_blog_content_agent], termination_condition=termination)

import asyncio

async def main():
    await Console(
        reflection_team.run_stream(task="""

                        I am writing a blog about machine learning. Answer the following 3 questions and write a blog and save it
                        
                        1. What is Machine Learning?
                        2. The difference between AI and ML
                        3. The history of Machine Learning
                                    

        """)
    )

asyncio.run(main())