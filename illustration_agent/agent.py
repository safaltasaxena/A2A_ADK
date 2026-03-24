import os
import uuid
import datetime
from dotenv import load_dotenv

# ADK imports
from google.adk import Agent
from google.adk.agents import SequentialAgent, LoopAgent, ParallelAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.models import Gemini
import sys
from google.adk.apps.app import App

from .plugins import Graceful429Plugin

from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from google import genai
from google.genai.types import GenerateContentConfig, ImageConfig, HttpOptions, HttpRetryOptions
from google.cloud import storage

load_dotenv()

# --- SDK Initialization ---
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")

graceful_plugin = Graceful429Plugin(
    name="graceful_429_plugin",
    fallback_text={
        "supporting": f"**[Simulated Response via 429 Graceful Fallback]**\n\n**Prompt used:** Two stylized figures in maintenance overalls giving each other a high-five under bright stadium lights. Flat corporate memphis style, purple and green geometric shapes.\n**Image URL:** https://storage.cloud.google.com/{project_id}-bucket/adk_and_a2a/illustration_agent/mock_images/generated_image1.png?authuser=0",
        "training": f"**[Simulated Response via 429 Graceful Fallback]**\n\n**Prompt used:** Illustration of employees in a stadium maintenance environment undergoing on-the-job training. Purple and green geometric memphis style.\n**Image URL:** https://storage.cloud.google.com/{project_id}-bucket/adk_and_a2a/illustration_agent/mock_images/generated_image2.png?authuser=0",
        "default": "**[Simulated Response via 429 Graceful Fallback]**\n\nThe image generation model or illustration agent is currently out of quota. Please retry later."
    }
)

RETRY_OPTIONS = HttpRetryOptions(initial_delay=1, attempts=6)

client = genai.Client(
    vertexai=True,
    project=project_id,
    location=location,
    http_options=HttpOptions(retry_options=RETRY_OPTIONS),
)


# ==============================================================================
# Tools
# ==============================================================================
def generate_image(prompt: str) -> dict[str, str]:
    """Generate an illustration, upload to GCS, and return a signed URL.

    Args:
        prompt (str): The prompt to provide to the image generation model.

    Returns:
        dict[str, str]: {"image_url": "The signed, time-limited public URL."}
    """
    # 1. Call the model
    try:
        response = client.models.generate_content(
            model=os.getenv("IMAGE_MODEL"),
            contents=prompt,
            config=GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=ImageConfig(
                    aspect_ratio="1:1",
                ),
                candidate_count=1,
            ),
        )
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
            print("\n[PLUGIN TRIGGERED] Caught 429 Error in Tool. Returning Graceful Fallback image.")
            if "training" in prompt.lower() or "mentorship" in prompt.lower() or "learning" in prompt.lower():
                return {"image_url": f"https://storage.cloud.google.com/{project_id}-bucket/adk_and_a2a/illustration_agent/mock_images/generated_image2.png?authuser=0"}
            return {"image_url": f"https://storage.cloud.google.com/{project_id}-bucket/adk_and_a2a/illustration_agent/mock_images/generated_image1.png?authuser=0"}
        raise e

    # 2. Extract the raw image data from the response
    image_bytes = response.candidates[0].content.parts[0].inline_data.data

    # 3. Upload the image bytes to Google Cloud Storage
    storage_client = storage.Client(project=project_id)
    bucket_name = f"{project_id}-bucket" 
    bucket = storage_client.bucket(bucket_name)
    
    # Generate a unique name for the image file
    blob_name = f"generated-images/{uuid.uuid4()}.png"
    blob = bucket.blob(blob_name)
    
    # Upload the data
    blob.upload_from_string(image_bytes, content_type="image/png")
    
    return {"image_url": f"https://storage.cloud.google.com/{bucket_name}/{blob_name}?authuser=0"}


# ==============================================================================
# Agent code
# ==============================================================================
root_agent = Agent(
    name="illustration_agent",
    model=Gemini(model=os.getenv("MODEL"), retry_options=RETRY_OPTIONS),
    description="Creates branded illustrations.",
    instruction="""
    You are an illustrator for a stadium maintenance company.

    You will receive a block of text, it is your job to write
    a prompt that will express the ideas of this text.

    You always emphasize that there should be no text in the image.
    You prefer a flat, geometric, corporate memphis diagrammatic style of art.
    Your brand palette is purple (#BF40BF), green (#DAF7A6), and sunset colors.
    Consider a clever or charming approach with specific details.
    Incorporate stadium imagery like lights, yardage indicators, green fields, popcorn.
    Incorporate maintenance imagery like wrenches, toolboxes, overalls.
    Incorporate general sports imagery like balls, caps, gloves.

    Once you have written the prompt, use your 'generate_image' tool to generate an image.
    Always return both of the following:
        - the text of the prompt you used
        - the generated image URL returned by your tool
    """,
    tools=[generate_image]
)

graceful_plugin.apply_429_interceptor(root_agent)

app = App(
    name="illustration_agent",
    root_agent=root_agent,
    plugins=[graceful_plugin]
)
# UNCOMMENT THE LINE BELOW TO TEST FAILOVER:
# graceful_plugin.apply_test_failover(root_agent)
