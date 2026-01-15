from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import httpx
from pathlib import Path
from openai import AsyncOpenAI

# Initialize router
router = APIRouter()

# Configuration
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Models
class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str

class GenerateRequest(BaseModel):
    transcript: str
    template_id: str
    provider: str = "ollama"  # "ollama" or "openai"
    model: str = "gemma2:2b"  # Default model
    api_key: Optional[str] = None  # For OpenAI
    custom_prompt: Optional[str] = None
    meeting_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SummaryResponse(BaseModel):
    summary: Dict[str, Any]
    raw_summary: Optional[str] = None
    model: str
    markdown: Optional[str] = None
    summary_json: Optional[List[Dict[str, Any]]] = None  # BlockNote blocks format

# Helper to load templates
def get_templates() -> List[Dict]:
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    
    for file in TEMPLATES_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                templates.append({
                    "id": file.stem,
                    "name": data.get("name", file.stem),
                    "description": data.get("description", "")
                })
        except Exception as e:
            print(f"Error loading template {file}: {e}")
    return templates

def get_template_content(template_id: str) -> Optional[Dict]:
    file_path = TEMPLATES_DIR / f"{template_id}.json"
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def json_to_blocknote(summary_data: dict, template: dict) -> List[Dict[str, Any]]:
    """Convert JSON summary to BlockNote blocks format"""
    blocks = []
    
    for section in template.get("sections", []):
        title = section["title"]
        content = summary_data.get(title)
        
        if not content:
            continue
        
        # Add section heading
        blocks.append({
            "id": f"heading-{len(blocks)}",
            "type": "heading",
            "props": {"level": 2, "textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
            "content": [{"type": "text", "text": title, "styles": {}}],
            "children": []
        })
        
        if isinstance(content, list):
            # Check if this list should be a table (List of Dicts)
            is_table = False
            table_rows = []
            
            if len(content) > 0:
                first_item = content[0]
                if isinstance(first_item, dict):
                    # List of dicts -> Table
                    is_table = True
                    # Get headers from first dict keys
                    headers = list(first_item.keys())
                    
                    # Create Header Row
                    header_cells = [[{"type": "text", "text": f"**{h}**", "styles": {"bold": True}}] for h in headers]
                    table_rows.append({"cells": header_cells})
                    
                    # Create Data Rows
                    for item in content:
                        if isinstance(item, dict):
                            row_cells = []
                            for h in headers:
                                val = str(item.get(h, ""))
                                row_cells.append([{"type": "text", "text": val, "styles": {}}])
                            table_rows.append({"cells": row_cells})
                            
                elif isinstance(first_item, str) and "|" in first_item:
                    # List of pipe-delimited strings -> Table
                    # Try to parse markdown table
                    is_table = True
                    for row_str in content:
                         # Skip divider rows
                         if set(row_str.strip()).issubset(set("|- ")):
                             continue
                             
                         # Parse cells
                         cells_text = [c.strip() for c in row_str.strip("|").split("|")]
                         row_cells = []
                         for c_text in cells_text:
                             # Check for bold syntax **text**
                             styles = {}
                             if c_text.startswith("**") and c_text.endswith("**"):
                                 c_text = c_text[2:-2]
                                 styles["bold"] = True
                             row_cells.append([{"type": "text", "text": c_text, "styles": styles}])
                         table_rows.append({"cells": row_cells})

            if is_table and table_rows:
                blocks.append({
                    "id": f"table-{len(blocks)}",
                    "type": "table",
                    "props": {"textColor": "default", "backgroundColor": "default"},
                    "content": {
                        "type": "tableContent",
                        "rows": table_rows
                    },
                    "children": []
                })
            else:
                # Regular list
                for item in content:
                    text_content = str(item)
                    if isinstance(item, dict):
                         text_content = " | ".join([f"**{k}**: {v}" for k, v in item.items()])
                         
                    blocks.append({
                        "id": f"block-{len(blocks)}",
                        "type": "bulletListItem",
                        "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
                        "content": [{"type": "text", "text": text_content, "styles": {}}],
                        "children": []
                    })

        elif isinstance(content, str):
            # Paragraph
            blocks.append({
                "id": f"block-{len(blocks)}",
                "type": "paragraph",
                "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
                "content": [{"type": "text", "text": content, "styles": {}}],
                "children": []
            })
            
        elif isinstance(content, dict):
             # Handle single dict content (treat as key-value list)
            text_content = " | ".join([f"**{k}**: {v}" for k, v in content.items()])
            blocks.append({
                "id": f"block-{len(blocks)}",
                "type": "paragraph",
                "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
                "content": [{"type": "text", "text": text_content, "styles": {}}],
                "children": []
            })
        else:
            print(f"⚠️ Warning: Unknown content type for section '{title}': {type(content)}")
    
    # DEBUG LOGGING (User requested)
    print(f"\n🧱 GENERATED BLOCKNOTE JSON DEBUG ({len(blocks)} blocks):")
    print("-" * 40)
    # Print first few blocks and any tables
    for i, b in enumerate(blocks):
        if b['type'] == 'table':
            print(f"[{i}] TABLE BLOCK: {json.dumps(b, ensure_ascii=False)[:200]}...")
        elif i < 10: # Print more blocks to debug missing sections
            print(f"[{i}] {b['type']}: {str(b.get('content', ''))[:100]}")
    print("-" * 40)

    return blocks

def json_to_markdown(summary_data: dict, template: dict) -> str:
    """Convert JSON summary to markdown format"""
    markdown = ""
    
    # DEBUG: Log all sections and their content types
    print(f"\n🔍 json_to_markdown DEBUG:")
    print(f"   Template has {len(template.get('sections', []))} sections")
    print(f"   Summary data has {len(summary_data)} keys: {list(summary_data.keys())}")
    for title, content in summary_data.items():
        content_type = type(content).__name__
        content_len = len(content) if isinstance(content, (list, str)) else "N/A"
        is_empty = not content or (isinstance(content, (list, str)) and len(content) == 0)
        print(f"   - '{title}': {content_type} (len={content_len}, empty={is_empty})")
    
    for section in template.get("sections", []):
        title = section["title"]
        content = summary_data.get(title)
        
        if not content:
            print(f"   ⏭️ Skipping '{title}' (no content)")
            continue
        
        # Add section title as H2
        markdown += f"## {title}\n\n"
        
        if isinstance(content, list):
            # Check if this list should be a table (List of Dicts)
            if len(content) > 0 and isinstance(content[0], dict):
                # Build Markdown Table
                try:
                    headers = list(content[0].keys())
                    markdown += "| " + " | ".join(headers) + " |\n"
                    markdown += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                    for item in content:
                        if isinstance(item, dict):
                            row = []
                            for h in headers:
                                raw_val = str(item.get(h, ""))
                                # Clean up newlines in table cells
                                clean_val = raw_val.replace("\n", " ")
                                row.append(clean_val)
                            markdown += "| " + " | ".join(row) + " |\n"
                    markdown += "\n"
                except Exception as e:
                    print(f"⚠️ Failed to build formatted table for {title}: {e}")
                    # Fallback to key-value list
                    for item in content:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                markdown += f"- **{k}**: {v}\n"
                        else:
                            markdown += f"- {item}\n"
                    markdown += "\n"
            else:
                for item in content:
                     # Check if it looks like a markdown table row (starts with |)
                    if isinstance(item, str) and item.strip().startswith("|"):
                        markdown += f"{item}\n"
                    else:
                        markdown += f"- {item}\n"
                markdown += "\n"
        elif isinstance(content, str):
            # Plain text paragraphs
            markdown += f"{content}\n\n"
    
    # DEBUG LOGGING (User requested)
    print(f"\n📝 GENERATED MARKDOWN DEBUG ({len(markdown)} chars):")
    print("-" * 40)
    print(markdown[:500] + "..." if len(markdown) > 500 else markdown)
    print("-" * 40)
    
    return markdown

    
    return markdown

async def extract_atomic_facts(transcript: str, provider: str, model: str, api_key: Optional[str] = None) -> List[Dict]:
    """
    Extract atomic facts from transcript using the Reframe/FRAME methodology.
    This acts as a grounding step to prevent hallucinations.
    """
    system_prompt = """You are an expert at breaking down meeting transcripts into atomic facts. Your task is to extract clear, factual statements with proper context.

IMPORTANT RULES:
1. Output must be a valid JSON list of objects
2. NEVER add information not in the transcript
3. Skip unclear or ambiguous content
4. Each fact must be atomic (single piece of information)
5. NO hallucination or inference

CONTENT GUIDELINES - STRICTLY FOLLOW:
1. INCLUDE only:
   - Clear, explicit statements
   - Complete, meaningful information
   - Actionable items or decisions
   - Important discussion points
   - Concrete facts or outcomes

2. EXCLUDE completely:
   - Filler statements (e.g., "OK", "Right", "Mm-hmm")
   - General acknowledgments
   - Incomplete or unclear statements
   - Transcription artifacts
   - Side conversations
   - Redundant information

3. For each included fact, provide:
   - "fact": Single, atomic piece of information
   - "context": Current chunk's context
   - "verbose_context": Historical context

Output Format:
Must return a JSON object with a single key "facts" containing a list of objects:
{
    "facts": [
        {
            "fact": "Clear atomic statement",
            "context": "Immediate context and implications",
            "verbose_context": "Comprehensive context with history",
            "timestamp": "Start time in seconds (float) or [MM:SS] string from source",
            "citation": "[MM:SS] format string"
        }
    ]
}"""

    user_prompt = f"""
    Break down this transcript chunk into atomic facts with context.
    
    Current chunk:
    {transcript}

    Provide output as a PURE JSON list (no markdown formatting).
    """

    try:
        if provider == "openai":
            if not api_key:
                raise ValueError("API Key required for OpenAI")
            
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1, # Low temperature for factual extraction
                max_completion_tokens=4096
            )
            content = response.choices[0].message.content
        else: # Ollama
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(OLLAMA_API_URL, json={
                    "model": model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_ctx": 8192
                    }
                })
                if response.status_code != 200:
                    raise Exception(f"Ollama error: {response.text}")
                    
                content = response.json().get("response", "")

        # Parse JSON
        content = content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.endswith("```"): content = content[:-3]
        
        try:
            parsed_content = json.loads(content)
            
            # OpenAI 'json_object' format forces a root object (dict), NOT a list
            # So looking for 'facts', 'items', 'content' keys is correct
            facts = []
            if isinstance(parsed_content, dict):
                 # Try common keys
                 for key in ['facts', 'items', 'statements', 'atomic_facts']:
                     if key in parsed_content and isinstance(parsed_content[key], list):
                         facts = parsed_content[key]
                         break
                 # If no list found, checking single object structure or list-like dict keys
                 if not facts and "fact" in parsed_content: # Single fact object
                     facts = [parsed_content]
            elif isinstance(parsed_content, list):
                 facts = parsed_content
            
            # Filter valid facts
            valid_facts = []
            for f in facts:
                if isinstance(f, dict) and "fact" in f and f["fact"]:
                    valid_facts.append(f)
            
            facts = valid_facts # Use filtered list
            if isinstance(facts, dict):
                # Check if it is a single fact object (has "fact" key)
                if "fact" in facts:
                     facts = [facts]
                else:
                    for k in ["facts", "atomic_facts", "items", "data", "response"]:
                        if k in facts and isinstance(facts[k], list):
                            facts = facts[k]
                            break
            
            if not isinstance(facts, list):
                print(f"⚠️ Warning: Atomic facts extraction returned {type(facts)} instead of list. Content: {content[:100]}...")
                return []

            # Filter out error messages masquerading as facts
            valid_facts = []
            for f in facts:
                fact_text = f.get("fact", "").lower()
                if "no clear" in fact_text and "explicit statements" in fact_text:
                    continue
                if "error" in fact_text and "transcript" in fact_text:
                    continue
                valid_facts.append(f)
            
            if len(valid_facts) == 0 and len(facts) > 0:
                 print("⚠️ Extracted facts appear to be error messages. Returning empty to trigger fallback.")
                 return []
                
            print(f"✅ Extracted {len(valid_facts)} atomic facts")
            return valid_facts
            
        except json.JSONDecodeError:
            print(f"❌ Failed to parse atomic facts JSON: {content[:100]}...")
            # Fallback: try to just use lines if it looks like a list
            return []
            
    except Exception as e:
        print(f"❌ Error extracting atomic facts: {str(e)}")
        # Fallback to returning original text as one fact
        return [{"fact": transcript, "context": "Raw transcript due to error", "verbose_context": ""}]

async def generate_with_openai(request: GenerateRequest, template: dict, system_prompt: str, user_prompt: str) -> SummaryResponse:
    """Generate summary using OpenAI API"""
    if not request.api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key is required")
    
    try:
        client = AsyncOpenAI(api_key=request.api_key)
        
        response = await client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_completion_tokens=4096
        )
        
        generated_text = response.choices[0].message.content
        
        # Parse JSON
        try:
            clean_text = generated_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            
            summary_data = json.loads(clean_text)
            
            # DEBUG: Show what OpenAI returned vs what template expects
            print(f"\n{'='*60}")
            print(f"📊 OPENAI JSON PARSING DEBUG")
            print(f"{'='*60}")
            print(f"✅ OpenAI returned keys: {list(summary_data.keys())}")
            print(f"✅ Template expects sections:")
            for section in template.get("sections", []):
                print(f"  - '{section['title']}'")
            print(f"{'='*60}\n")
            
            # Handle different response formats
            # If OpenAI returned template structure (with 'sections' array), extract the data
            if 'sections' in summary_data and isinstance(summary_data['sections'], list):
                print("⚠️ OpenAI returned template format - extracting data from sections array")
                # Rebuild as flat dict keyed by section title
                flattened = {}
                for section_data in summary_data['sections']:
                    if isinstance(section_data, dict) and 'title' in section_data:
                        title = section_data['title']
                        content = section_data.get('content') or section_data.get('items') or section_data.get('text', '')
                        flattened[title] = content
                summary_data = flattened
                print(f"✅ Flattened to keys: {list(summary_data.keys())}")
            
            # Convert to formats
            markdown = json_to_markdown(summary_data, template)
            # blocknote_blocks = json_to_blocknote(summary_data, template)  # DISABLED - using markdown only
            
            # Also create legacy format for compatibility
            legacy_summary = {}
            for section in template.get("sections", []):
                title = section["title"]
                content = summary_data.get(title)
                
                if content:
                    blocks = []
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                text = " | ".join([f"**{k}**: {v}" for k,v in item.items()])
                                blocks.append({"content": text, "type": "paragraph", "id": f"{title}-{len(blocks)}"})
                            else:
                                blocks.append({"content": str(item), "type": "bulletListItem", "id": f"{title}-{len(blocks)}"})
                    elif isinstance(content, str):
                        blocks.append({"content": content, "type": "paragraph", "id": f"{title}-0"})
                        
                    legacy_summary[title] = {
                        "title": title,
                        "blocks": blocks
                    }
            
            return SummaryResponse(
                summary=legacy_summary,
                markdown=markdown,
                summary_json=None,  # DISABLED: Using pure markdown for reliability
                raw_summary=generated_text,
                model=request.model
            )
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON from OpenAI: {generated_text}")
            print(f"Error: {e}")
            # Return raw text as markdown
            return SummaryResponse(
                summary={
                    "Error": {
                        "title": "Error Parsing Summary",
                        "blocks": [{"content": "The model response was not valid JSON.", "type": "paragraph", "id": "error-0"}]
                    }
                },
                markdown=f"## Error\n\n{generated_text}",
                raw_summary=generated_text,
                model=request.model
            )
            
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenAI API Error: {str(e)}")

async def generate_with_ollama(request: GenerateRequest, template: dict, system_prompt: str, user_prompt: str) -> SummaryResponse:
    """Generate summary using Ollama"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(OLLAMA_API_URL, json={
                "model": request.model,
                "prompt": user_prompt,
                "system": system_prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 8192
                }
            })
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Ollama Error: {response.text}")
            
            result = response.json()
            generated_text = result.get("response", "")
            
            # Parse JSON
            try:
                clean_text = generated_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                
                summary_data = json.loads(clean_text)
                
                # Handle different response formats (same as OpenAI)
                if 'sections' in summary_data and isinstance(summary_data['sections'], list):
                    print("⚠️ Ollama returned template format - extracting data from sections array")
                    flattened = {}
                    for section_data in summary_data['sections']:
                        if isinstance(section_data, dict) and 'title' in section_data:
                            title = section_data['title']
                            content = section_data.get('content') or section_data.get('items') or section_data.get('text', '')
                            flattened[title] = content
                    summary_data = flattened
                    print(f"✅ Flattened to keys: {list(summary_data.keys())}")
                
                # Convert to formats
                markdown = json_to_markdown(summary_data, template)
                # blocknote_blocks = json_to_blocknote(summary_data, template)  # DISABLED
                
                # Also create legacy format
                legacy_summary = {}
                for section in template.get("sections", []):
                    title = section["title"]
                    content = summary_data.get(title)
                    
                    if content:
                        blocks = []
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    text = " | ".join([f"**{k}**: {v}" for k,v in item.items()])
                                    blocks.append({"content": text, "type": "paragraph", "id": f"{title}-{len(blocks)}"})
                                else:
                                    blocks.append({"content": str(item), "type": "bulletListItem", "id": f"{title}-{len(blocks)}"})
                        elif isinstance(content, str):
                            blocks.append({"content": content, "type": "paragraph", "id": f"{title}-0"})
                            
                        legacy_summary[title] = {
                            "title": title,
                            "blocks": blocks
                        }
                
                return SummaryResponse(
                    summary=legacy_summary,
                    markdown=markdown,
                    summary_json=None,  # DISABLED: Using pure markdown
                    raw_summary=generated_text,
                    model=request.model
                )

            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON from Ollama: {generated_text}")
                print(f"Error: {e}")
                return SummaryResponse(
                    summary={
                        "Error": {
                            "title": "Error Parsing Summary",
                            "blocks": [{"content": "The model response was not valid JSON.", "type": "paragraph", "id": "error-0"}]
                        }
                    },
                    markdown=f"## Error\n\n{generated_text}",
                    raw_summary=generated_text,
                    model=request.model
                )

    except httpx.RequestError as e:
         raise HTTPException(status_code=503, detail=f"Could not connect to Ollama service: {e}")

# Routes
@router.get("/templates", response_model=List[TemplateInfo])
async def list_templates():
    """List available summary templates"""
    return get_templates()

@router.post("/generate", response_model=SummaryResponse)
async def generate_summary(request: GenerateRequest):
    """Generate summary using selected provider (Ollama or OpenAI)"""
    
    try:
        # 1. Load Template
        template = get_template_content(request.template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template {request.template_id} not found")

        # 2. Extract Atomic Facts (Reframe/FRAME Methodology)
        print(f"\n🚀 STARTING REFRAME PIPELINE...")
        print(f"1️⃣ Extracting Atomic Facts (Groundedness Check)...")
        
        # Use a timeout or safeguards if needed, but for now we trust the helper
        atomic_facts = await extract_atomic_facts(
            request.transcript, 
            request.provider, 
            request.model, 
            request.api_key
        )
        
        # Format facts for the generator
        facts_text = json.dumps(atomic_facts, ensure_ascii=False, indent=2)
        print(f"✅ Fact Extraction Complete. Found {len(atomic_facts)} facts.")

        # 3. Construct Improved Prompt (inspired by desktop app's Pydantic approach)
        
        # 4. Inject Metadata Context
        metadata_context = ""
        if request.metadata:
            metadata_context = f"""
THÔNG TIN CUỘC HỌP (SỬ DỤNG CHO PHẦN THÔNG TIN CHUNG):
- Tiêu đề: {request.metadata.get('meeting_title', 'Không xác định')}
- Thời gian: {request.metadata.get('date', 'Không xác định')}
- Danh sách tham dự: {', '.join(request.metadata.get('participants', [])) if request.metadata.get('participants') else 'Không xác định'}
"""

        system_prompt = f"""Bạn là một thư ký cuộc họp chuyên nghiệp. Nhiệm vụ là tạo biên bản họp CHẤT LƯỢNG CAO từ danh sách "Atomic Facts" (Sự kiện đã xác thực).

{metadata_context}

CẤU TRÚC TEMPLATE:
{json.dumps(template, ensure_ascii=False, indent=2)}

HƯỚNG DẪN CHI TIẾT:"""
        
        for section in template.get("sections", []):
            system_prompt += f"\n- **{section['title']}**: {section['instruction']}"
        
        system_prompt += f"""

ĐỊNH DẠNG OUTPUT JSON:
{{
  "Section Title 1": <content>,
  "Section Title 2": <content>,
  ...
}}

QUY TẮC NỘI DUNG:
- Content có thể là STRING (paragraph) hoặc ARRAY (danh sách items)
- Nếu là array items, mỗi item có thể là string hoặc object với key-value pairs
- VÍ DỤ danh sách người: {{"name": "Nguyễn Văn A", "role": "Trưởng phòng"}}
- Sửa lỗi chính tả nếu có, văn phong trang trọng, chuyên nghiệp.
- CHỈ SỬ DỤNG thông tin từ "SOURCE ATOMIC FACTS". Không bịa đặt thêm.
- Nêu đầy đủ action items, deadlines, decisions
- Nếu section không có info → trả về empty string "" hoặc empty array []

CITATION RULES (QUAN TRỌNG):
- Với mỗi facts quan trọng được sử dụng, CẦN kèm theo timestamp citation ở cuối câu.
- Format: `[MM:SS]` (Ví dụ: `[12:30]`, `[01:05]`)
- Citations phải chính xác với timestamp của Source Fact.
- KHÔNG tự bịa ra timestamp.

CRITICAL: Trả về PURE JSON, KHÔNG có ```json wrapper, KHÔNG có text dẫn dắt."""

        # Prepare input for summary generation
        if atomic_facts and len(atomic_facts) > 0:
            user_prompt_content = f"""SOURCE ATOMIC FACTS (SỬ DỤNG NHỮNG SỰ KIỆN NÀY ĐỂ VIẾT BIÊN BẢN):
---
{facts_text}
---"""
            print("✅ Using ATOMIC FACTS for generation.")
        else:
            print("⚠️ Atomic facts empty. Falling back to RAW TRANSCRIPT.")
            print(f"   📏 Transcript length: {len(request.transcript)} chars")
            print(f"   📄 Transcript preview (first 200 chars): {request.transcript[:200]}...")
            user_prompt_content = f"""SOURCE TRANSCRIPT (SỬ DỤNG NỘI DUNG NÀY ĐỂ VIẾT BIÊN BẢN):
---
{request.transcript}
---"""

        user_prompt = f"""{user_prompt_content}

NGỮ CẢNH BỔ SUNG:
{request.custom_prompt if request.custom_prompt else "Không có"}

Hãy tạo biên bản họp chi tiết theo template dựa trên thông tin đã cung cấp. Output phải là RAW JSON."""

        # 3. Generate based on provider
        result = None
        if request.provider == "openai":
            result = await generate_with_openai(request, template, system_prompt, user_prompt)
        else:  # Default to ollama
            result = await generate_with_ollama(request, template, system_prompt, user_prompt)
        
        # Debug logging
        print(f"\n{'='*60}")
        print(f"🎯 SUMMARY RESPONSE DEBUG")
        print(f"{'='*60}")
        print(f"✅ Provider: {request.provider}")
        print(f"✅ Model: {result.model}")
        print(f"✅ Has markdown: {result.markdown is not None}")
        if result.markdown:
            print(f"✅ Markdown length: {len(result.markdown)} chars")
            print(f"✅ Markdown preview (first 200 chars):\n{result.markdown[:200]}...")
        print(f"✅ Has summary: {result.summary is not None}")
        print(f"✅ Summary keys: {list(result.summary.keys()) if result.summary else []}")
        if result.summary:
            for key, value in list(result.summary.items())[:2]:  # First 2 sections
                print(f"  - Section '{key}': {len(value.get('blocks', []))} blocks")
        print(f"✅ Has raw_summary: {result.raw_summary is not None}")
        print(f"{'='*60}\n")
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in generate_summary: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
