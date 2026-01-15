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
            "props": {"level": 2, "textColor": "default", "backgroundColor": "default"},
            "content": [{"type": "text", "text": title, "styles": {}}],
            "children": []
        })
        
        # Add content blocks
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    # Format as table row or bullet with key-value
                    text = " | ".join([f"**{k}**: {v}" for k, v in item.items()])
                    blocks.append({
                        "id": f"block-{len(blocks)}",
                        "type": "bulletListItem",
                        "props": {"textColor": "default", "backgroundColor": "default"},
                        "content": [{"type": "text", "text": text, "styles": {}}],
                        "children": []
                    })
                else:
                    # Simple bullet item
                    blocks.append({
                        "id": f"block-{len(blocks)}",
                        "type": "bulletListItem",
                        "props": {"textColor": "default", "backgroundColor": "default"},
                        "content": [{"type": "text", "text": str(item), "styles": {}}],
                        "children": []
                    })
        elif isinstance(content, str):
            # Paragraph
            blocks.append({
                "id": f"block-{len(blocks)}",
                "type": "paragraph",
                "props": {"textColor": "default", "backgroundColor": "default"},
                "content": [{"type": "text", "text": content, "styles": {}}],
                "children": []
            })
    
    return blocks

def json_to_markdown(summary_data: dict, template: dict) -> str:
    """Convert JSON summary to markdown format"""
    markdown = ""
    
    for section in template.get("sections", []):
        title = section["title"]
        content = summary_data.get(title)
        
        if not content:
            continue
        
        # Add section title as H2
        markdown += f"## {title}\n\n"
        
        if isinstance(content, list):
            # Lists - each item gets a bullet
            for item in content:
                if isinstance(item, dict):
                    # Format dict as key: value pairs
                    for k, v in item.items():
                        markdown += f"- **{k}**: {v}\n"
                else:
                    markdown += f"- {item}\n"
            markdown += "\n"
        elif isinstance(content, str):
            # Plain text paragraphs
            markdown += f"{content}\n\n"
    
    return markdown

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
            max_tokens=4096
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
            blocknote_blocks = json_to_blocknote(summary_data, template)
            
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
                summary_json=blocknote_blocks,
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
                blocknote_blocks = json_to_blocknote(summary_data, template)
                
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
                    summary_json=blocknote_blocks,
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

        # 2. Construct Improved Prompt (inspired by desktop app's Pydantic approach)
        system_prompt = f"""Bạn là một thư ký cuộc họp chuyên nghiệp. Nhiệm vụ là tạo biên bản họp CHẤT LƯỢNG CAO từ transcript.

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
- Sửa lỗi chính tả nếu có
- Nêu đầy đủ action items, deadlines, decisions
- Nếu section không có info → trả về empty string "" hoặc empty array []

CRITICAL: Trả về PURE JSON, KHÔNG có ```json wrapper, KHÔNG có text dẫn dắt."""

        user_prompt = f"""NỘI DUNG TRANSCRIPT:
---
{request.transcript}
---

NGỮ CẢNH BỔ SUNG:
{request.custom_prompt if request.custom_prompt else "Không có"}

Hãy tạo biên bản họp chi tiết theo template. Output phải là RAW JSON."""

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
