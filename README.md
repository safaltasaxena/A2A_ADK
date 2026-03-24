

# **Complete A2A_ADK Lab Notes: From Scratch**

## **PART 1: UNDERSTANDING THE CONCEPTS**

### **What is A2A (Agent2Agent)?**
- **Problem It Solves**: Different AI agents built on different frameworks by different companies can't easily communicate with each other.
- **Solution**: A2A provides a common protocol for agents to communicate and collaborate—treating them as agents, not just tools.

### **Core A2A Concepts:**

1. **Standardized Communication**: JSON-RPC 2.0 over HTTP(S)
   - All agents speak the same language
   - RESTful communication between remote agents

2. **Agent Discovery**: Agent Cards
   - JSON file describing what an agent can do
   - Contains capabilities, endpoints, and authentication info
   - Allows agents to discover each other

3. **Rich Data Exchange**: 
   - Text, files, and structured JSON data
   - Images, documents, etc.

4. **Flexible Interaction**:
   - **Synchronous**: Request → Response
   - **Streaming**: Server-Sent Events (SSE)
   - **Asynchronous**: Push notifications

5. **Enterprise-Ready**:
   - Security, authentication, observability built-in

---

## **PART 2: TOOLS USED**

### **ADK (Agent Development Kit)**
- Framework for building AI agents using Google's generative AI
- Simplifies agent creation and deployment
- Integrates with Vertex AI and Gemini models

### **A2A SDK**
- Allows agents to call other agents remotely
- `RemoteA2aAgent` class for connecting to remote agents
- Reads Agent Cards to understand capabilities

### **Google Cloud Services**
- **Vertex AI**: LLM and image generation models
- **Cloud Run**: Deploy agents as serverless services
- **Cloud Storage (GCS)**: Store generated images

### **Google Gen AI SDK**
- Direct access to Gemini models
- Image generation capabilities
- Streaming and retry logic

---

## **PART 3: REAL-WORLD SCENARIO**

**Company**: Cymbal Stadiums (stadium maintenance company)

**Problem**: 
- Built an image generation agent for internal use
- Multiple teams want to use it
- Copying code everywhere = maintenance nightmare

**Solution**:
- Deploy the illustration agent once as a remote A2A service
- Other agents call it remotely when needed
- Centralized maintenance and updates

---

## **PART 4: LAB STRUCTURE**

```
adk_and_a2a/
├── illustration_agent/          # Agent that generates images
│   ├── agent.py                 # Main agent logic
│   ├── agent.json               # Agent Card (metadata)
│   ├── plugins.py               # Error handling plugin
│   ├── requirements.txt          # Dependencies
│   ├── __init__.py              
│   ├── .env                     # Environment variables
│   └── .adk/                    # ADK configuration
│
├── slide_content_agent/         # Agent that creates slide content
│   ├── agent.py                 # Main agent logic
│   ├── plugins.py               # Error handling plugin
│   ├── __init__.py
│   ├── .adk/
│   └── .env
│
└── illustration-agent-card.json # Copy of agent card for reference
```

---

## **PART 5: DETAILED CODE BREAKDOWN**

### **FILE 1: `illustration_agent/agent.py`**

#### **Imports Section (Lines 1-22)**

```python
import os
import uuid
import datetime
from dotenv import load_dotenv

# ADK Framework
from google.adk import Agent
from google.adk.agents import SequentialAgent, LoopAgent, ParallelAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.models import Gemini
import sys
from google.adk.apps.app import App

# Error handling
from .plugins import Graceful429Plugin

# A2A Protocol
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

# Google AI and Cloud
from google import genai
from google.genai.types import GenerateContentConfig, ImageConfig, HttpOptions, HttpRetryOptions
from google.cloud import storage

load_dotenv()
```

**What Each Import Does**:
- `load_dotenv()`: Loads environment variables from `.env` file
- `Agent`: Base class for creating agents
- `Gemini`: Model class for using Gemini LLM
- `App`: Wrapper to run agents as services
- `genai.Client`: Low-level client for Gemini API
- `storage.Client`: Google Cloud Storage access
- `Graceful429Plugin`: Custom error handling plugin

#### **Configuration Section (Lines 24-44)**

```python
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")

graceful_plugin = Graceful429Plugin(
    name="graceful_429_plugin",
    fallback_text={
        "supporting": f"**[Simulated Response via 429 Graceful Fallback]**\n\n**Prompt used:** Two stylized figures...",
        "training": f"**[Simulated Response via 429 Graceful Fallback]**\n\n**Prompt used:** Illustration of employees...",
        "default": "**[Simulated Response via 429 Graceful Fallback]**\n\nThe image generation model is currently out of quota."
    }
)
```

**Purpose**:
- Get GCP project ID and location from environment
- Create error handling plugin with fallback responses
- When quota is exhausted (429 error), serve pre-made fallback responses based on keywords
- Graceful degradation instead of complete failure

#### **Retry Configuration (Lines 37-44)**

```python
RETRY_OPTIONS = HttpRetryOptions(initial_delay=1, attempts=6)

client = genai.Client(
    vertexai=True,
    project=project_id,
    location=location,
    http_options=HttpOptions(retry_options=RETRY_OPTIONS),
)
```

**What This Does**:
- Create a Gemini client with automatic retry logic
- Initial delay: 1 second
- Maximum 6 retry attempts
- Helps handle temporary failures gracefully

#### **Tool Function: `generate_image()` (Lines 50-95)**

```python
def generate_image(prompt: str) -> dict[str, str]:
    """Generate an illustration, upload to GCS, and return a signed URL.
    
    Args:
        prompt (str): The prompt to provide to the image generation model.
    
    Returns:
        dict[str, str]: {"image_url": "The signed, time-limited public URL."}
    """
```

**Three-Step Process**:

**Step 1: Call the Image Generation Model (Lines 60-71)**
```python
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
```
- Use Gemini to generate a 1:1 aspect ratio image
- Return one candidate (image)

**Step 2: Error Handling (Lines 72-78)**
```python
except Exception as e:
    if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
        print("\n[PLUGIN TRIGGERED] Caught 429 Error in Tool. Returning Graceful Fallback image.")
        if "training" in prompt.lower() or "mentorship" in prompt.lower():
            return {"image_url": f"https://storage.cloud.google.com/{project_id}-bucket/adk_and_a2a/illustration_agent/mock_images/generated_image2.png?authuser=0"}
        return {"image_url": f"https://storage.cloud.google.com/{project_id}-bucket/adk_and_a2a/illustration_agent/mock_images/generated_image1.png?authuser=0"}
    raise e
```
- Check if error is a quota exhausted error (429)
- Return mock images from storage based on keywords
- Re-raise other errors

**Step 3: Upload to GCS and Return URL (Lines 80-95)**
```python
# Extract the raw image data
image_bytes = response.candidates[0].content.parts[0].inline_data.data

# Create GCS client and upload
storage_client = storage.Client(project=project_id)
bucket_name = f"{project_id}-bucket" 
bucket = storage_client.bucket(bucket_name)

blob_name = f"generated-images/{uuid.uuid4()}.png"  # Unique filename
blob = bucket.blob(blob_name)

blob.upload_from_string(image_bytes, content_type="image/png")

return {"image_url": f"https://storage.cloud.google.com/{bucket_name}/{blob_name}?authuser=0"}
```
- Extract raw image bytes from response
- Create unique filename using UUID
- Upload to GCS bucket
- Return public URL

#### **Agent Definition (Lines 101-125)**

```python
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
```

**How It Works**:

1. **Agent Setup**:
   - Give the agent a name and description
   - Use Gemini model with retry logic
   - Provide detailed instructions with brand guidelines

2. **Brand Guidelines** (embedded in instruction):
   - Style: Corporate Memphis (flat, geometric)
   - Colors: Purple, green, sunset
   - Imagery: Stadium, maintenance, sports
   - No text in images

3. **Tool Assignment**:
   - Agent has access to `generate_image` function
   - Agent can decide when to call it

4. **Error Plugin**:
   - `apply_429_interceptor()` wraps the agent to catch quota errors
   - Returns graceful fallback instead of failing

5. **App Wrapper**:
   - Makes the agent runnable as a service
   - Includes plugins for error handling

---

### **FILE 2: `illustration_agent/plugins.py`**

This file implements the `Graceful429Plugin` class for handling quota errors gracefully.

#### **Class Definition (Lines 5-10)**

```python
class Graceful429Plugin(BasePlugin):
    """Intercepts local failures to Vertex AI and handles them globally."""
    
    def __init__(self, name: str, fallback_text: str | dict):
        super().__init__(name=name)
        self.fallback_text = fallback_text
```

**Purpose**: Create a reusable error handling plugin that can be applied to any agent.

#### **Key Method: `_get_fallback_text()` (Lines 12-35)**

```python
def _get_fallback_text(self, request_contents) -> str:
    """Determines the correct fallback text by scanning the prompt for keywords."""
    if isinstance(self.fallback_text, str):
        return self.fallback_text
        
    # Convert request to lowercase string
    req_str = str(request_contents).lower()
    
    best_keyword = None
    best_index = -1
    
    # Find the latest (rightmost) matching keyword
    for keyword, response in self.fallback_text.items():
        if keyword == "default":
            continue
        idx = req_str.rfind(keyword.lower())  # rfind = rightmost find
        if idx > best_index:
            best_index = idx
            best_keyword = keyword
            
    if best_keyword:
        return self.fallback_text[best_keyword]
            
    # Fallback to default if no keywords matched
    return self.fallback_text.get("default", "**[System]** Quota exhausted. Please try again later.")
```

**Smart Fallback Logic**:
- If fallback is a single string, return it
- If dict of fallbacks, scan the user's request for keywords
- Use the **rightmost** keyword match (most recent in prompt)
- Example: If prompt contains "training" at position 150 and "stadium" at position 45, use "training" response
- Fall back to "default" if no keywords match

#### **Hook: `on_model_error()` (Lines 37-56)**

```python
async def on_model_error(self, *, agent, model, input, error: Exception) -> LlmResponse | None:
    """Standard ADK hook for handling model-level exceptions."""
    if "RESOURCE_EXHAUSTED" in str(error) or "429" in str(error):
        print(f"\n[PLUGIN TRIGGERED] Caught 429 Error. Returning Graceful Fallback for {self.name}.")
        
        fallback = self._get_fallback_text(input)
        return LlmResponse(
            content=types.Content(
                role="model", 
                parts=[types.Part.from_text(text=fallback)]
            )
        )
    return None
```

**How It Works**:
- ADK calls this hook when model encounters an error
- Check if error is quota-related (429 or RESOURCE_EXHAUSTED)
- Get appropriate fallback text using keyword matching
- Return a fake LLM response with fallback text
- User gets a response instead of a crash

#### **Method: `apply_429_interceptor()` (Lines 104-136)**

```python
def apply_429_interceptor(self, agent):
    '''Surgically wraps the agent's model to catch real 429s.'''
    targets = []
    if hasattr(agent, 'sub_agents') and agent.sub_agents:
        for sub_agent in agent.sub_agents:
            if hasattr(sub_agent, 'model'): 
                targets.append(sub_agent.model)
    else:
        if hasattr(agent, 'model'): 
            targets.append(agent.model)

    for target in targets:
        if not hasattr(target, 'generate_content_async'):
            continue
        original_method = getattr(target, 'generate_content_async')
        
        async def wrapped_429_failover(*args, **kwargs):
            try:
                async for result in original_method(*args, **kwargs):
                    yield result
            except Exception as e:
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                    print(f"\n[PLUGIN TRIGGERED] Caught real 429 Error.")
                    request_contents = args[0] if len(args) > 0 else kwargs
                    fallback = self._get_fallback_text(request_contents)
                    yield LlmResponse(
                        content=types.Content(
                            role="model", 
                            parts=[types.Part.from_text(text=fallback)]
                        )
                    )
                else:
                    raise
                    
        object.__setattr__(target, 'generate_content_async', wrapped_429_failover)
```

**Advanced Error Handling**:
- Uses monkey-patching to intercept model calls
- Wraps the async `generate_content_async` method
- Catches 429 errors during streaming
- Yields graceful fallback response instead of failing
- Handles both single agents and agents with sub-agents

---

### **FILE 3: `illustration_agent/agent.json`**

This is the Agent Card—metadata describing the agent for A2A protocol.

```json
{
    "name": "illustration_agent",
    "description": "An agent designed to generate branded illustrations for Cymbal Stadiums.",
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["application/json"],
    "skills": [
    {
        "id": "illustrate_text",
        "name": "Illustrate Text",
        "description": "Generate an illustration to illustrate the meaning of provided text.",
        "tags": ["illustration", "image generation"]
    }
    ],
    "url": "https://illustration-agent-PROJECT_NUMBER.REGION.run.app/a2a/illustration_agent",
    "capabilities": {},
    "version": "1.0.0"
}
```

**What Each Field Does**:

| Field | Purpose |
|-------|---------|
| `name` | Identifier for the agent |
| `description` | Human-readable description |
| `defaultInputModes` | What types of input it accepts (text/plain) |
| `defaultOutputModes` | What types of output it returns (JSON) |
| `skills` | Array of things the agent can do |
| `url` | Endpoint where the agent is deployed (Cloud Run URL) |
| `capabilities` | Advanced features (streaming, etc.) - empty for basic agent |
| `version` | Version number for updates |

**Skills Definition**:
```json
{
    "id": "illustrate_text",           // Unique ID
    "name": "Illustrate Text",         // Display name
    "description": "...",              // What it does
    "tags": ["illustration", ...]      // Categories for discovery
}
```

---

### **FILE 4: `slide_content_agent/agent.py`**

This agent creates slide content AND calls the illustration agent remotely.

#### **Key Difference: RemoteA2aAgent (Lines 25-31)**

```python
illustration_agent = RemoteA2aAgent(
    name="illustration_agent",
    description="Agent that generates illustrations.",
    agent_card=(
        "illustration-agent-card.json"
    ),
)
```

**What This Does**:
- Creates a reference to the **remote** illustration agent
- Reads the Agent Card (`illustration-agent-card.json`) to understand capabilities
- Prepares to call the remote agent via A2A protocol
- The JSON file contains the Cloud Run URL and other metadata

#### **Main Agent with Sub-Agent (Lines 32-45)**

```python
root_agent = LlmAgent(
    model=Gemini(model=os.getenv("MODEL"), retry_options=RETRY_OPTIONS),
    name='slide_content_agent',
    description='An agent that writes content for slide decks.',
    instruction="""
        A user will ask you to create content for a slide to communicate an idea.
        Write a short headline about this idea.
        Write 1-2 sentences of body text about this idea.
        Share these with the user.
        Then transfer to the 'illustration_agent' to generate an illustration related to this idea.
        """,
    sub_agents=[illustration_agent]  # KEY LINE!
)
```

**How Sub-Agents Work**:

1. **User Input**: "Create content for a slide about our excellent on-the-job training."

2. **Step 1 - Headline & Body** (slide_content_agent):
   - Agent generates: "Level Up On the Job!"
   - Body: "At Cymbal Stadiums, we provide hands-on training..."

3. **Step 2 - Transfer** (automatic):
   - Agent calls `illustration_agent` (via A2A protocol)
   - Sends the text to remote agent

4. **Step 3 - Image Generation** (illustration_agent):
   - Remote agent receives text
   - Generates image based on text + brand guidelines
   - Returns image URL

5. **Step 4 - Final Response**:
   - slide_content_agent returns to user:
     - Headline
     - Body text
     - Image URL from illustration_agent

---

### **FILE 5: `slide_content_agent/plugins.py`**

Identical to `illustration_agent/plugins.py`—reusable error handling plugin.

---

## **PART 6: STEP-BY-STEP EXECUTION FLOW**

### **Phase 1: Setup (Local Development)**

```bash
# 1. Download code and install ADK
gcloud storage cp -r gs://PROJECT_ID-bucket/* .
export PATH=$PATH:"/home/${USER}/.local/bin"
python3 -m pip install --upgrade google-adk a2a-sdk google-genai

# 2. Set environment variables
cat << EOF > illustration_agent/.env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GOOGLE_CLOUD_LOCATION=global
MODEL=gemini_flash_model_id
IMAGE_MODEL=gemini_flash_image_model_id
EOF

# 3. Copy .env to other agent
cp illustration_agent/.env slide_content_agent/.env

# 4. Test locally
adk web  # Opens http://localhost:8000
```

**What Happens**:
- ADK loads both agents
- Dev UI lets you test agents locally
- Test illustration_agent with: "By supporting each other, we get big things done!"
- Agent creates prompt respecting brand guidelines and generates image

---

### **Phase 2: Deploy to Cloud Run (Expose as A2A Service)**

```bash
# Deploy illustration_agent as A2A service
adk deploy cloud_run \
    --project YOUR_GCP_PROJECT_ID \
    --region us-west4 \
    --service_name illustration-agent \
    --a2a \
    illustration_agent
```

**What Happens**:
1. **Dockerfile Creation**: ADK creates a Dockerfile for the agent
2. **Build**: Builds Docker image with all dependencies
3. **Push**: Pushes to Google Cloud Container Registry
4. **Deploy**: Deploys to Cloud Run
5. **URL Generation**: Creates public URL like `https://illustration-agent-PROJECT.us-west4.run.app`
6. **A2A Wrapping**: Wraps agent with `A2aAgentExecutor` bridge
7. **Agent Card Hosting**: Serves Agent Card at `/a2a/illustration_agent/.well-known/agent.json`

**Result**:
- illustration_agent is now accessible remotely
- Other agents can discover it via Agent Card
- Communication via JSON-RPC 2.0 over HTTP(S)

---

### **Phase 3: Remote Agent Integration**

```python
# In slide_content_agent/agent.py
illustration_agent = RemoteA2aAgent(
    name="illustration_agent",
    description="Agent that generates illustrations.",
    agent_card="illustration-agent-card.json"
)

root_agent = LlmAgent(
    ...,
    sub_agents=[illustration_agent]
)
```

**What Happens**:

1. **Read Agent Card**: Load `illustration-agent-card.json` 
2. **Extract URL**: Get Cloud Run URL from Agent Card
3. **Register Sub-Agent**: Tell LlmAgent about remote agent
4. **Enable Transfer**: Agent can now call remote agent

---

### **Phase 4: User Interaction Flow**

**User Input**: "Create content for a slide about our excellent on-the-job training."

```
┌─────────────────────────────────────────────────────────────────────┐
│ USER                                                                │
├─────────────────────────────────────────────────────────────────────┤
│ Input: "Create content for a slide about on-the-job training."      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ SLIDE_CONTENT_AGENT (Local)                                        │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Gemini generates headline & body text                            │
│ 2. Output: "Level Up On the Job!"                                   │
│            "At Cymbal Stadiums, we provide hands-on training..."    │
│ 3. Calls: transfer_to_agent("illustration_agent", user_text)       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    HTTP(S) over A2A Protocol
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ILLUSTRATION_AGENT (Remote on Cloud Run)                           │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Receive text via JSON-RPC 2.0                                    │
│ 2. Gemini writes image prompt:                                      │
│    "Illustration of employees in stadium environment undergoing     │
│     on-the-job training. Purple and green geometric memphis style." │
│ 3. Calls generate_image(prompt)                                     │
│ 4. Model generates image → upload to GCS → return URL               │
│ 5. Response: {"prompt": "...", "image_url": "gs://..."}            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    HTTP(S) JSON Response
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ SLIDE_CONTENT_AGENT (Back)                                         │
├─────────────────────────────────────────────────────────────────────┤
│ Receives image URL from remote agent                                │
│ Returns complete response to user:                                  │
│ - Headline: "Level Up On the Job!"                                  │
│ - Body: "At Cymbal Stadiums..."                                     │
│ - Image URL: [clickable link to generated image]                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ USER                                                                │
├─────────────────────────────────────────────────────────────────────┤
│ ✅ Sees complete slide content with generated image                │
│ ✅ Can click image URL to preview                                   │
│ ✅ All from a single prompt!                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## **PART 7: KEY DESIGN PATTERNS**

### **Pattern 1: Tool Functions**
```python
def generate_image(prompt: str) -> dict[str, str]:
    """Agent can call this function"""
    # Do work
    return {"image_url": "..."}
```

**Purpose**: Give agents specific capabilities via Python functions

---

### **Pattern 2: Sub-Agents**
```python
remote_agent = RemoteA2aAgent(
    name="illustration_agent",
    agent_card="illustration-agent-card.json"
)

root_agent = LlmAgent(
    ...,
    sub_agents=[remote_agent]
)
```

**Purpose**: Allow agents to delegate work to other agents (local or remote)

---

### **Pattern 3: Error Handling Plugin**
```python
class Graceful429Plugin(BasePlugin):
    def on_model_error(self, *, agent, model, input, error):
        # Catch errors
        # Return graceful fallback
```

**Purpose**: Prevent failures from cascading; provide fallback responses

---

### **Pattern 4: Agent Card Discovery**
```json
{
    "name": "illustration_agent",
    "url": "https://...",
    "skills": [...]
}
```

**Purpose**: Let agents discover and understand each other's capabilities

---

### **Pattern 5: A2A Protocol Bridge**
- ADK agents deployed with `--a2a` flag get wrapped
- `A2aAgentExecutor` translates between ADK and A2A protocols
- JSON-RPC 2.0 communication over HTTP(S)

**Purpose**: Enable cross-framework communication

---

## **PART 8: IMPORTANT CONCEPTS TO REMEMBER**

### **What is JSON-RPC 2.0?**
- Standard for remote procedure calls
- Request/Response format for HTTP(S)
- Example:
  ```json
  Request: {
    "jsonrpc": "2.0",
    "method": "transfer_to_agent",
    "params": {"agent": "illustration_agent", "text": "..."},
    "id": 1
  }
  
  Response: {
    "jsonrpc": "2.0",
    "result": {"image_url": "..."},
    "id": 1
  }
  ```

---

### **What is Graceful Degradation?**
- System fails gracefully instead of completely
- Example: If image generation quota is exhausted:
  - **Bad**: Error screen, user can't proceed
  - **Good**: Return pre-made image, user gets results

---

### **What is Monkey Patching?**
```python
original_method = getattr(target, 'generate_content_async')

async def wrapped_method(*args, **kwargs):
    try:
        async for result in original_method(*args, **kwargs):
            yield result
    except Exception as e:
        # Handle error

object.__setattr__(target, 'generate_content_async', wrapped_method)
```

- Dynamically replace a method at runtime
- Used to add error handling without modifying original code
- Powerful but use carefully!

---

### **What is Agent Card (in A2A)?**
- JSON metadata file describing agent capabilities
- Equivalent to an API documentation
- Contains: name, description, skills, endpoint URL, version
- Enables agent discovery and capability negotiation

---

## **PART 9: DEPLOYMENT ARCHITECTURE**

```
┌──────────────────────────────────────────────────────────┐
│                   Your GCP Project                       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Cloud Run: illustration-agent Service             │ │
│  ├────────────────────────────────────────────────────┤ │
│  │ • Runs Docker container with agent code           │ │
│  │ • URL: https://illustration-agent-PROJECT.run.app │ │
│  │ • Endpoint: /a2a/illustration_agent               │ │
│  │ • Agent Card: /.well-known/agent.json             │ │
│  └────────────────────────────────────────────────────┘ │
│                         ▲                                │
│                         │                                │
│                   (HTTP/HTTPS)                           │
│                         │                                │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Local Development (adk web)                        │ │
│  ├────────────────────────────────────────────────────┤ │
│  │ • slide_content_agent (local)                      │ │
│  │ • Reads Agent Card                                 │ │
│  │ • Calls remote illustration_agent                  │ │
│  │ • Gets image URL back                              │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Cloud Storage Bucket                               │ │
│  ├────────────────────────────────────────────────────┤ │
│  │ • Stores generated images                          │ │
│  │ • generated-images/[uuid].png                      │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## **PART 10: SUMMARY OF WHAT YOU LEARNED**

### **What You Did:**

1. ✅ **Installed ADK** - Set up Agent Development Kit
2. ✅ **Built illustration_agent** - Agent that generates branded images
3. ✅ **Created Agent Card** - JSON metadata for A2A discovery
4. ✅ **Deployed to Cloud Run** - Made agent publicly accessible
5. ✅ **Built slide_content_agent** - Agent that uses remote agent
6. ✅ **Integrated via A2A** - Remote agent calling over HTTP(S)
7. ✅ **Tested end-to-end** - User prompt → slide content + image

### **Why This Matters:**

| Problem | Solution | Benefit |
|---------|----------|---------|
| Code duplication | Deploy once as service | Single source of truth |
| Maintenance nightmare | Centralized agent | Update in one place |
| Framework lock-in | A2A protocol | Use any framework |
| Talent silos | Agent discovery via Card | Reuse across teams |
| Single point of failure | Graceful degradation | Users still get value |

### **Real-World Applications:**

- **Cross-Company**: Company A's image agent called by Company B's app
- **Microservices**: Break monolithic agent into specialized agents
- **Load Distribution**: Deploy agents across multiple regions
- **A/B Testing**: Route requests to different agent versions
- **Disaster Recovery**: Failover to backup agent endpoints

---

## **PART 11: FILES QUICK REFERENCE**

| File | Purpose | Key Classes |
|------|---------|-------------|
| `illustration_agent/agent.py` | Image generation agent | `Agent`, `Gemini` |
| `illustration_agent/agent.json` | Agent metadata for A2A | JSON structure |
| `illustration_agent/plugins.py` | Error handling | `Graceful429Plugin` |
| `slide_content_agent/agent.py` | Slide content agent with sub-agent | `LlmAgent`, `RemoteA2aAgent` |
| `slide_content_agent/plugins.py` | Same error plugin | `Graceful429Plugin` |
| `.env` files | Configuration | Environment variables |

---

## **PART 12: ENVIRONMENT VARIABLES EXPLAINED**

```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE          # Use Vertex AI instead of direct API
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID    # GCP Project ID
GOOGLE_CLOUD_LOCATION=global             # Vertex AI location
MODEL=gemini_flash_model_id              # LLM model to use
IMAGE_MODEL=gemini_flash_image_model_id  # Image generation model
```

---

## **PART 13: COMMANDS USED IN LAB**

```bash
# Install
python3 -m pip install --upgrade google-adk a2a-sdk google-genai

# Local testing
adk web                                   # Start dev UI at localhost:8000

# Deployment
adk deploy cloud_run \
    --project YOUR_PROJECT_ID \
    --region us-west4 \
    --service_name illustration-agent \
    --a2a \
    illustration_agent
```

---

## **PART 14: TROUBLESHOOTING NOTES**

| Issue | Cause | Solution |
|-------|-------|----------|
| 403 Forbidden Error | Multiple Google accounts signed in | Increment `authuser` parameter |
| 429 Error | API quota exhausted | Plugin returns fallback image |
| PERMISSION_DENIED | IAM permissions | Retry deployment command |
| Module not found | Missing dependencies | Install with pip |
| .env not loaded | Wrong directory | Create in agent directory |

---

## **CONCLUSION**

This lab demonstrated **Agent2Agent (A2A) protocol** for building interconnected AI systems. You:

1. Created specialized agents (illustration, slide content)
2. Deployed one as a remote service on Cloud Run
3. Called it from another agent using A2A protocol
4. Handled errors gracefully with custom plugins
5. Discovered agents via Agent Cards

This architecture enables:
- ✅ **Scalability**: Multiple teams using one agent
- ✅ **Maintainability**: Update agent once, all users benefit
- ✅ **Interoperability**: Agents from different frameworks communicate
- ✅ **Resilience**: Graceful degradation on failures
- ✅ **Flexibility**: Compose complex workflows from simple agents

**The Future**: Imagine a world where AI agents from different companies cooperate seamlessly—that's what A2A enables! 🚀
