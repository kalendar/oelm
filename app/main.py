from fastapi import FastAPI, WebSocket, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv
from groq import Groq
import json
from pathlib import Path

# Load environment variables
load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Groq client
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

def load_markdown_files(directory: Path) -> dict:
    """Load all markdown files from a directory into a dictionary."""
    files = {}
    for md_file in directory.glob("*.md"):
        topic = md_file.stem
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            files[topic] = content
    return files

def load_system_components():
    """Load both contexts and pedagogies from their respective directories."""
    app_dir = Path(__file__).parent
    contexts = load_markdown_files(app_dir / "contexts")
    pedagogies = load_markdown_files(app_dir / "pedagogy")
    return contexts, pedagogies

def create_system_prompt(context: str, pedagogy: str, greeting: str) -> dict:
    """Combine context and pedagogy into a system prompt."""
    return {
        "role": "system",
        "content": f"{pedagogy}\n\n{context}\n\n{greeting}"
    }

CONTEXTS, PEDAGOGIES = load_system_components()

GREETING = "Greet the user by saying: 'Hi! I'm LOLA, the Lumen One Learning Assistant. Let's review some key statistics concepts together. This review doesn't count toward your grade - it's just for *you*. And please remember that, because I'm an AI, I can make mistakes sometimes. Ready to start our review?'"

@app.get("/")
async def root(
    request: Request, 
    context: str = Query(default="probability"),
    pedagogy: str = Query(default="interactive_review")
):
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "context": context,
            "pedagogy": pedagogy
        }
    )

@app.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket, 
    context: str = Query(default="probability"),
    pedagogy: str = Query(default="interactive_review")
):
    await websocket.accept()
    print(f"WebSocket connected. Context: {context}, Pedagogy: {pedagogy}")
    
    selected_context = CONTEXTS.get(context, CONTEXTS["probability"])
    selected_pedagogy = PEDAGOGIES.get(pedagogy, PEDAGOGIES["interactive_review"])
    
    # Start with just the system message
    context_content = selected_context["content"] if isinstance(selected_context, dict) else selected_context
    pedagogy_content = selected_pedagogy["content"] if isinstance(selected_pedagogy, dict) else selected_pedagogy
    
    system_prompt = str(create_system_prompt(context_content, pedagogy_content, GREETING))
    print(f"System prompt: {system_prompt}")  # Debug log
    
    messages = [{
        "role": "system", 
        "content": system_prompt
    }]
    
    # Get initial response
    print("Getting initial response...")  # Debug log
    response = await get_chat_response(messages, websocket)
    print(f"Initial response: {response}")  # Debug log
    messages.append({"role": "assistant", "content": response})
    
    # Send an empty chunk to ensure the frontend renders the response
    await websocket.send_text("\n")
    
    while True:
        try:
            data = await websocket.receive_json()
            messages.append({"role": "user", "content": data["content"]})
            response = await get_chat_response(messages, websocket)
            messages.append({"role": "assistant", "content": response})
            await websocket.send_text("\n")  # Ensure message completion
            
        except WebSocketDisconnect:
            print("WebSocket disconnected")
            break
        except Exception as e:
            print(f"Error: {e}")
            await websocket.send_json({"error": str(e)})
            break

async def get_chat_response(messages: list, websocket) -> str:
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
#            model="llama-3.3-70b-versatile",
            model="llama-3.1-8b-instant",
            stream=True
        )
        
        full_response = ""
        for chunk in chat_completion:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
        
        # Send the complete response at once
        await websocket.send_text(full_response)
        # Send an empty message to signal completion
        await websocket.send_text("\n")
        return full_response
        
    except Exception as e:
        print(f"Error in get_chat_response: {e}")
        raise e