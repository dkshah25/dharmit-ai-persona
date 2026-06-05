import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import openai
from dotenv import load_dotenv

# Import our backend modules
from ingest import ingest_data
from rag import build_vector_store, query_vector_store
from scheduler import get_slots, create_booking
from guardrails import is_adversarial_prompt, get_fallback_response

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize FastAPI App
app = FastAPI(title="Scaler AI Persona Platform API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Client adaptively: Use free Groq or Gemini if present (Groq is preferred here since user's Gemini key has generateContent limit 0)
if GROQ_API_KEY:
    print("[Server] Initializing Client with Groq API (100% Free & Low Latency)")
    openai_client = openai.AsyncOpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    LLM_MODEL = "llama-3.1-8b-instant"
elif GEMINI_API_KEY:
    print("[Server] Initializing Client with Google Gemini API (100% Free)")
    openai_client = openai.AsyncOpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    LLM_MODEL = "gemini-2.5-flash" # Use 2.5-flash as the fallback model name
else:
    print("[Server] Initializing Client with OpenAI API")
    openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    LLM_MODEL = "gpt-4o-mini"

# Pydantic schemas
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = True

class BookRequest(BaseModel):
    start_time: str
    name: str
    email: str
    notes: Optional[str] = ""

# OpenAI Tool Schemas
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_available_slots",
            "description": "Checks available interview time slots for the next few days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Optional start date in YYYY-MM-DD format."
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Optional end date in YYYY-MM-DD format."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Books an interview slot for the recruiter. Requires slot start time, recruiter's name, and email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "The selected start time in ISO format (e.g. 2026-06-05T10:00:00.000Z)."
                    },
                    "name": {
                        "type": "string",
                        "description": "Recruiter's full name."
                    },
                    "email": {
                        "type": "string",
                        "description": "Recruiter's email address."
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes or message."
                    }
                },
                "required": ["start_time", "name", "email"]
            }
        }
    }
]

def get_system_prompt(rag_context: str) -> str:
    return (
        "You are the professional AI representative of Dharmit Shah.\n"
        "Your purpose is to answer recruiter questions about Dharmit's resume, projects, engineering decisions, and tradeoffs, and to help them book an interview.\n\n"
        "Persona Guidelines:\n"
        "- Introduce yourself as Dharmit's AI representative when appropriate.\n"
        "- Explain that you are trained on Dharmit's public work, resume, and GitHub repositories.\n"
        "- Keep answers professional, concise, and conversational.\n"
        "- Since you are used in a voice channel as well, keep spoken answers brief and easy to understand (avoid long lists of bullet points unless asked).\n"
        "- Speak in the first person representing Dharmit's AI agent (e.g., \"I can tell you about Dharmit's experience...\" or \"Dharmit built...\").\n"
        "- You have access to scheduling tools: `check_available_slots` and `book_appointment`. Use them when the recruiter wants to book an interview or check availability.\n\n"
        "RAG Context Instructions:\n"
        "- You are provided with retrieved context from Dharmit's resume and GitHub profile below.\n"
        "- Rely ONLY on the provided context. If the context does not contain the answer to a factual question, you MUST respond exactly with: \"I do not have enough information in my knowledge base to answer that accurately.\"\n"
        "- Never invent details or assume facts. If a question is outside the scope of the provided data, politely say so using the fallback message.\n\n"
        f"--- START RETRIEVED CONTEXT ---\n{rag_context}\n--- END RETRIEVED CONTEXT ---"
    )

async def safe_chat_completion(model, messages, stream=False, temperature=0.3, tools=None, tool_choice=None):
    """
    Calls openai_client.chat.completions.create with fallback rotation for 429 RateLimitErrors.
    """
    import openai
    
    # Define a rotation of fallback models to bypass free-tier rate limits
    models_to_try = [model]
    for fallback in ["llama-3.3-70b-versatile", "allam-2-7b"]:
        if fallback != model and fallback not in models_to_try:
            models_to_try.append(fallback)
            
    # Try each model in sequence immediately on 429
    for current_model in models_to_try:
        try:
            kwargs = {
                "model": current_model,
                "messages": messages,
                "stream": stream,
                "temperature": temperature
            }
            if tools is not None:
                kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
                
            return await openai_client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "rate limit" in err_str or "429" in err_str or "limit" in err_str or "quota" in err_str or "503" in err_str or "overloaded" in err_str or isinstance(e, openai.RateLimitError):
                print(f"[LLM Rate Limit/Overload] Hit error for model {current_model}. Rotating to fallback model...")
                continue
            else:
                raise e
                
    # If all models in the rotation hit 429, fall back to waiting/retry loop on the original model
    print("[LLM Rate Limit] All fallback models rate-limited/overloaded. Falling back to wait-and-retry loop...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "stream": stream,
                "temperature": temperature
            }
            if tools is not None:
                kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
                
            return await openai_client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "rate limit" in err_str or "429" in err_str or "limit" in err_str or "quota" in err_str or "503" in err_str or "overloaded" in err_str or isinstance(e, openai.RateLimitError):
                wait_time = 10 * (attempt + 1)
                print(f"[LLM Rate Limit Backup] Hit error for model {model}. Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
            else:
                raise e
                
    raise HTTPException(status_code=429, detail="LLM rate limits exceeded for all fallback models.")

async def handle_tool_execution(name: str, arguments: str) -> Dict[str, Any]:
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except Exception:
        args = {}
    
    if name == "check_available_slots":
        slots = get_slots(args.get("start_date"), args.get("end_date"))
        return {
            "success": True,
            "slots": slots,
            "message": f"Found {len(slots)} available slots. Suggest some to the user."
        }
    elif name == "book_appointment":
        res = create_booking(
            start_time=args.get("start_time"),
            name=args.get("name"),
            email=args.get("email"),
            notes=args.get("notes", "")
        )
        return res
    return {"success": False, "error": f"Unknown tool: {name}"}

def get_resume_path() -> str:
    # Try local backend/data/resume.pdf first (used in Render production where rootDir is backend)
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(backend_dir, "data", "resume.pdf")
    if os.path.exists(local_path):
        return local_path
    # Fallback to parent workspace dir
    workspace_dir = os.path.dirname(backend_dir)
    return os.path.join(workspace_dir, "data", "resume.pdf")

@app.get("/api/status")
async def get_status():
    """
    Check availability of resources and keys
    """
    resume_path = get_resume_path()
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")
    
    active_tunnel_url = None
    tunnel_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_url.txt")
    if os.path.exists(tunnel_file):
        try:
            with open(tunnel_file, "r", encoding="utf-8") as f:
                active_tunnel_url = f.read().strip()
        except Exception:
            pass

    return {
        "openai_configured": (OPENAI_API_KEY is not None) or (GEMINI_API_KEY is not None) or (GROQ_API_KEY is not None),
        "github_configured": os.getenv("GITHUB_TOKEN") is not None,
        "cal_configured": os.getenv("CAL_API_KEY") is not None,
        "resume_uploaded": os.path.exists(resume_path),
        "vector_db_built": os.path.exists(os.path.join(db_path, "vectors.json")),
        "active_tunnel_url": active_tunnel_url
    }

@app.post("/api/ingest")
async def trigger_ingestion():
    """
    Triggers resume parser and github ingestion, then builds ChromaDB index.
    """
    if not OPENAI_API_KEY and not GEMINI_API_KEY and not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Neither OPENAI_API_KEY nor GEMINI_API_KEY nor GROQ_API_KEY configured in backend .env")
        
    resume_path = get_resume_path()
    processed_dir = os.path.join(workspace_dir, "data", "processed")
    
    # Run ingestion script functions
    try:
        num_repos = ingest_data(resume_path, processed_dir)
        db_built = build_vector_store(processed_dir)
        return {
            "success": db_built,
            "repositories_ingested": num_repos,
            "message": "Successfully ingested resume and GitHub repositories, and updated ChromaDB."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.get("/api/slots")
async def fetch_slots(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Returns available slots from scheduler
    """
    slots = get_slots(start_date, end_date)
    return {"slots": slots}

@app.post("/api/book")
async def book_slot(req: BookRequest):
    """
    Creates booking slot
    """
    res = create_booking(req.start_time, req.name, req.email, req.notes)
    if res.get("success"):
        return res
    raise HTTPException(status_code=400, detail=res.get("error", "Booking failed"))

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Standard chat completion endpoint supporting streaming responses,
    RAG, and prompt injection defense.
    """
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured.")
        
    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty.")
        
    last_user_message = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    
    # 1. Guardrails prompt injection check
    is_adv, defense_msg = is_adversarial_prompt(last_user_message)
    if is_adv:
        if req.stream:
            async def defense_stream():
                yield f"data: {json.dumps({'choices': [{'delta': {'content': defense_msg}, 'finish_reason': None}]})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(defense_stream(), media_type="text/event-stream")
        else:
            return JSONResponse(content={"content": defense_msg})
            
    # 2. RAG Context retrieval
    # Retrieve top 5 matches
    results, max_confidence = query_vector_store(last_user_message, top_k=5)
    
    rag_context = ""
    sources = []
    if results:
        rag_context_list = []
        for r in results:
            rag_context_list.append(r["content"])
            # Track sources (prevent duplicates)
            source_meta = r["metadata"]
            source_name = "Resume" if source_meta.get("source") == "resume" else f"GitHub: {source_meta.get('repository')}"
            url = source_meta.get("url", "")
            if {"name": source_name, "url": url} not in sources:
                sources.append({"name": source_name, "url": url})
        rag_context = "\n\n".join(rag_context_list)
        
    # Build OpenAI system prompt with retrieved context
    system_prompt = get_system_prompt(rag_context)
    
    # Re-build OpenAI message list
    api_messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history
    for msg in req.messages:
        api_messages.append({"role": msg.role, "content": msg.content})
        
    if req.stream:
        async def stream_generator():
            try:
                # Add sources as a special initial payload or in chunks.
                # We can output a custom JSON chunk first containing the sources.
                yield f"data: {json.dumps({'sources': sources})}\n\n"
                
                response = await safe_chat_completion(
                    model=LLM_MODEL,
                    messages=api_messages,
                    stream=True,
                    temperature=0.3,
                    tools=TOOLS,
                    tool_choice="auto"
                )
                
                tool_calls_to_exec = []
                
                async for chunk in response:
                    delta = chunk.choices[0].delta
                    
                    # Accumulate tool calls if any
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            if len(tool_calls_to_exec) <= tc.index:
                                tool_calls_to_exec.append({
                                    "id": tc.id,
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments or ""
                                })
                            else:
                                if tc.id:
                                    tool_calls_to_exec[tc.index]["id"] = tc.id
                                if tc.function.name:
                                    tool_calls_to_exec[tc.index]["name"] = tc.function.name
                                tool_calls_to_exec[tc.index]["arguments"] += tc.function.arguments or ""
                    
                    if delta.content:
                        yield f"data: {json.dumps({'choices': [{'delta': {'content': delta.content}, 'finish_reason': chunk.choices[0].finish_reason}]})}\n\n"
                
                # If tool calls were requested, execute them and stream second response
                if tool_calls_to_exec:
                    # Append tool calls to message history
                    api_messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]}
                            }
                            for tc in tool_calls_to_exec
                        ]
                    })
                    
                    for tc in tool_calls_to_exec:
                        # Yield a system indicator to frontend
                        yield f"data: {json.dumps({'status': 'Executing tool: ' + tc['name']})}\n\n"
                        tool_result = await handle_tool_execution(tc["name"], tc["arguments"])
                        
                        # Add tool response
                        api_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": json.dumps(tool_result)
                        })
                        
                    # Call OpenAI again with the tool output
                    second_response = await safe_chat_completion(
                        model=LLM_MODEL,
                        messages=api_messages,
                        stream=True,
                        temperature=0.3
                    )
                    
                    async for chunk in second_response:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            yield f"data: {json.dumps({'choices': [{'delta': {'content': delta.content}, 'finish_reason': chunk.choices[0].finish_reason}]})}\n\n"
                            
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"
                
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # Non-streaming fallback
        try:
            response = await safe_chat_completion(
                model=LLM_MODEL,
                messages=api_messages,
                temperature=0.3,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            if message.tool_calls:
                api_messages.append(message)
                for tc in message.tool_calls:
                    tool_result = await handle_tool_execution(tc.function.name, tc.function.arguments)
                    api_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": json.dumps(tool_result)
                    })
                
                second_response = await safe_chat_completion(
                    model=LLM_MODEL,
                    messages=api_messages,
                    temperature=0.3
                )
                return JSONResponse(content={"content": second_response.choices[0].message.content, "sources": sources})
                
            return JSONResponse(content={"content": message.content, "sources": sources})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vapi/custom-llm/chat/completions")
@app.post("/api/vapi/custom-llm")
async def vapi_custom_llm(request: Request):
    """
    Vapi Custom LLM API endpoint.
    Vapi calls this with OpenAI chat-completions structure, expecting 
    OpenAI-compatible streaming response. We intercept and apply our RAG retrieval
    and guardrail defenses.
    """
    print("\n[Server] === Received Vapi Custom LLM Request ===")
    if not openai_client:
        print("[Server] Error: openai_client not initialized!")
        return JSONResponse(status_code=500, content={"error": "OpenAI not configured"})
        
    body = await request.json()
    vapi_messages = body.get("messages", [])
    stream = body.get("stream", True)
    print(f"[Server] Stream: {stream}, Message Count: {len(vapi_messages)}")
    if vapi_messages:
        print(f"[Server] Last Message: {vapi_messages[-1]}")
    
    # Identify user's last message
    last_user_message = ""
    for msg in reversed(vapi_messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
            
    # 1. Guardrails
    is_adv, defense_msg = is_adversarial_prompt(last_user_message)
    if is_adv:
        # Vapi is calling an OpenAI-compatible endpoint. We return chunks
        async def vapi_defense_stream():
            chunk = {
                "choices": [{
                    "delta": {"content": defense_msg},
                    "finish_reason": None,
                    "index": 0
                }],
                "id": "vapi-guardrail",
                "object": "chat.completion.chunk",
                "model": LLM_MODEL
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            
            chunk_done = {
                "choices": [{
                    "delta": {},
                    "finish_reason": "stop",
                    "index": 0
                }],
                "id": "vapi-guardrail",
                "object": "chat.completion.chunk",
                "model": LLM_MODEL
            }
            yield f"data: {json.dumps(chunk_done)}\n\n"
            yield "data: [DONE]\n\n"
            
        return StreamingResponse(vapi_defense_stream(), media_type="text/event-stream")

    # 2. RAG Retrieval
    results, max_confidence = query_vector_store(last_user_message, top_k=3)
    rag_context = ""
    if results:
        rag_context = "\n\n".join([r["content"] for r in results])
        
    system_prompt = get_system_prompt(rag_context)
    
    # Formulate API messages
    api_messages = [{"role": "system", "content": system_prompt}]
    for m in vapi_messages:
        # Skip the original system prompt that Vapi sent since we override it
        if m.get("role") == "system":
            continue
        api_messages.append({
            "role": m.get("role"),
            "content": m.get("content")
        })
        
    # Call OpenAI with Vapi tools or our default tools
    vapi_tools = body.get("tools") or TOOLS
    
    if stream:
        async def vapi_stream_generator():
            try:
                response = await safe_chat_completion(
                    model=LLM_MODEL,
                    messages=api_messages,
                    stream=True,
                    temperature=0.2,
                    tools=vapi_tools
                )
                
                tool_calls_to_exec = []
                
                async for chunk in response:
                    delta = chunk.choices[0].delta
                    
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            if len(tool_calls_to_exec) <= tc.index:
                                tool_calls_to_exec.append({
                                    "id": tc.id,
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments or ""
                                })
                            else:
                                if tc.id:
                                    tool_calls_to_exec[tc.index]["id"] = tc.id
                                if tc.function.name:
                                    tool_calls_to_exec[tc.index]["name"] = tc.function.name
                                tool_calls_to_exec[tc.index]["arguments"] += tc.function.arguments or ""
                    
                    # Yield OpenAI chunk format back to Vapi
                    chunk_dict = chunk.model_dump()
                    yield f"data: {json.dumps(chunk_dict)}\n\n"
                    
                if tool_calls_to_exec:
                    # Append tool calls to message history
                    api_messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]}
                            }
                            for tc in tool_calls_to_exec
                        ]
                    })
                    
                    for tc in tool_calls_to_exec:
                        tool_result = await handle_tool_execution(tc["name"], tc["arguments"])
                        api_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": json.dumps(tool_result)
                        })
                        
                    second_response = await safe_chat_completion(
                        model=LLM_MODEL,
                        messages=api_messages,
                        stream=True,
                        temperature=0.2
                    )
                    
                    async for chunk in second_response:
                        chunk_dict = chunk.model_dump()
                        yield f"data: {json.dumps(chunk_dict)}\n\n"
                        
                yield "data: [DONE]\n\n"
            except Exception as e:
                # Return error chunk
                chunk_err = {
                    "choices": [{
                        "delta": {"content": f"I encountered an error: {str(e)}"},
                        "finish_reason": "stop",
                        "index": 0
                    }],
                    "id": "vapi-error",
                    "object": "chat.completion.chunk",
                    "model": LLM_MODEL
                }
                yield f"data: {json.dumps(chunk_err)}\n\n"
                yield "data: [DONE]\n\n"
                
        return StreamingResponse(vapi_stream_generator(), media_type="text/event-stream")
    else:
        # Non-streaming implementation for Vapi
        try:
            response = await safe_chat_completion(
                model=LLM_MODEL,
                messages=api_messages,
                temperature=0.2,
                tools=vapi_tools
            )
            
            message = response.choices[0].message
            if message.tool_calls:
                api_messages.append(message)
                for tc in message.tool_calls:
                    tool_result = await handle_tool_execution(tc.function.name, tc.function.arguments)
                    api_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": json.dumps(tool_result)
                    })
                second_response = await safe_chat_completion(
                    model=LLM_MODEL,
                    messages=api_messages,
                    temperature=0.2
                )
                return JSONResponse(content=second_response.model_dump())
                
            return JSONResponse(content=response.model_dump())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/evals/results")
async def get_eval_results():
    """
    Retrieves the evaluation results JSON if they exist.
    """
    eval_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evals", "results.json")
    if os.path.exists(eval_file):
        with open(eval_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "Evaluation results not found. Run evaluations first."}

@app.post("/api/evals/run")
async def run_evals_trigger():
    """
    Trigger evaluation script execution asynchronously.
    """
    workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    eval_script = os.path.join(workspace_dir, "evals", "run_evals.py")
    
    if not os.path.exists(eval_script):
        raise HTTPException(status_code=404, detail="Evaluation script not found")
        
    # We will trigger the evaluation script in a background process
    # so we don't block the API thread
    import subprocess
    import sys
    try:
        # Run it asynchronously using the same Python interpreter
        process = subprocess.Popen(
            [sys.executable, eval_script],
            cwd=workspace_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return {"success": True, "message": "Evaluation suite started in the background."}
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to start evaluation suite: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
