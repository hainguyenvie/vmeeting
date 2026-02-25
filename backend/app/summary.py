from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from pathlib import Path
from openai import AsyncOpenAI
import sqlite3
from app.database import get_db_path
import re

# Initialize router
router = APIRouter()

# Configuration - Read from environment variables (NO hardcoded secrets)
# Set these in your .env file or system environment:
#   LLM_BASE_URL=https://your-llm-endpoint/v1
#   LLM_API_KEY=your-api-key-here
#   LLM_MODEL=your-model-name
VIETTEL_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")  # Default: local Ollama
VIETTEL_API_KEY = os.getenv("LLM_API_KEY", "not-needed")                  # Required: set in .env
VIETTEL_DEFAULT_MODEL = os.getenv("LLM_MODEL", "qwen2.5:72b")             # Default: local model

TEMPLATE_FILE = Path("app/templates/bien_ban_hop_vn.json")
print(f"📋 Using fixed template: {TEMPLATE_FILE}")

# Models
class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str

class GenerateRequest(BaseModel):
    transcript: str
    template_id: str
    # Legacy fields kept for API compatibility but ignored/forced in logic
    provider: str = "viettel"
    model: str = VIETTEL_DEFAULT_MODEL
    api_key: Optional[str] = None
    custom_prompt: Optional[str] = None
    meeting_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SummaryResponse(BaseModel):
    summary: Dict[str, Any]
    raw_summary: Optional[str] = None
    model: str
    markdown: Optional[str] = None
    html: Optional[str] = None  # NEW: HTML format
    summary_json: Optional[List[Dict[str, Any]]] = None

# Helper to load templates
def get_templates() -> List[Dict]:
    """Return the single fixed template info"""
    return [{
        "id": "bien_ban_hop_vn",
        "name": "Biên bản họp (Vietnamese)",
        "description": "Template biên bản họp chuyên nghiệp (fixed)"
    }]

def get_template_content(template_id: str = None) -> Optional[Dict]:
    """
    Load the fixed template file.
    template_id parameter is ignored - always uses bien_ban_hop_vn.json
    """
    if not os.path.exists(TEMPLATE_FILE):
        print(f"❌ Template file not found at: {TEMPLATE_FILE}")
        return None
    
    try:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            template = json.load(f)
        return template
    except Exception as e:
        print(f"❌ Error loading template: {e}")
        return None

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
    
    return markdown

def markdown_to_html(markdown_text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Convert markdown summary to simple, clean HTML.
    Minimalist style matching standard document editors.
    """
    import re
    
    # We remove the hardcoded meeting_title and date injection here
    # because the LLM already generates "Thông tin chung" including "Thời gian"
    # in the markdown based on the template. Prepending it again creates duplicates.
    html = ""
    
    # Helper to parse inline formatting
    def format_inline(text: str) -> str:
        # Bold: **text** -> <strong>text</strong>
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        # Italic: *text* -> <em>text</em>
        text = re.sub(r'\*(?!\*)(.*?)\*', r'<em>\1</em>', text)
        # Citations: [MM:SS] -> <span class="citation">[MM:SS]</span>
        text = re.sub(r'\[(\d{1,2}:\d{2})\]', r'<span class="citation">[\1]</span>', text)
        return text

    # Parse markdown line by line
    lines = markdown_text.split('\n')
    in_table = False
    in_list = False
    in_ordered_list = False
    
    for line in lines:
        stripped = line.strip()
        
        # Empty lines
        if not stripped:
            if in_table:
                html += '</tbody></table>'
                in_table = False
            elif in_list:
                html += '</ul>'
                in_list = False
            elif in_ordered_list:
                html += '</ol>'
                in_ordered_list = False
            continue
        
        # Headers (H1, H2, H3)
        header_match = re.match(r'^(#{1,3})\s+(.*)', stripped)
        if header_match:
            if in_table:
                html += '</tbody></table>'
                in_table = False
            if in_list:
                html += '</ul>'
                in_list = False
            if in_ordered_list:
                html += '</ol>'
                in_ordered_list = False
                
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            title = format_inline(title)
            html += f'<h{level}>{title}</h{level}>'
            continue
        
        # Tables
        if stripped.startswith('|'):
            if in_list:
                html += '</ul>'
                in_list = False
            if in_ordered_list:
                html += '</ol>'
                in_ordered_list = False
            
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            
            if not cells:
                continue
                
            if all(set(c) <= {'-', ':', ' '} for c in cells if c):
                continue
            
            if not in_table:
                # Add border attributes for better compatibility with editors/email
                html += '<table border="1" cellpadding="5" cellspacing="0"><thead><tr>'
                for cell in cells:
                    html += f'<th>{format_inline(cell)}</th>'
                html += '</tr></thead><tbody>'
                in_table = True
            else:
                html += '<tr>'
                for cell in cells:
                    html += f'<td>{format_inline(cell)}</td>'
                html += '</tr>'
            continue
        
        # Bullet Lists
        if stripped.startswith('- ') or stripped == '-':
            if in_table:
                html += '</tbody></table>'
                in_table = False
            if in_ordered_list:
                html += '</ol>'
                in_ordered_list = False
            if not in_list:
                html += '<ul>'
                in_list = True
            
            text = stripped[2:].strip() if stripped.startswith('- ') else ""
            html += f'<li>{format_inline(text)}</li>'
            continue
            
        # Ordered Lists
        ordered_match = re.match(r'^\d+\.\s+(.*)', stripped)
        if ordered_match:
            if in_table:
                html += '</tbody></table>'
                in_table = False
            if in_list:
                html += '</ul>'
                in_list = False
            if not in_ordered_list:
                html += '<ol>'
                in_ordered_list = True
                
            text = ordered_match.group(1).strip()
            html += f'<li>{format_inline(text)}</li>'
            continue
        
        # Paragraphs
        if in_table:
            html += '</tbody></table>'
            in_table = False
        if in_list:
            html += '</ul>'
            in_list = False
        if in_ordered_list:
            html += '</ol>'
            in_ordered_list = False
            
        html += f'<p>{format_inline(stripped)}</p>'
    
    # Close any open tags at end
    if in_table:
        html += '</tbody></table>'
    if in_list:
        html += '</ul>'
    if in_ordered_list:
        html += '</ol>'
    
    return html

def clean_model_output(data: Any) -> Any:
    """Recursively clean strings in JSON output from LLMs."""
    if isinstance(data, dict):
        return {k: clean_model_output(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_model_output(item) for item in data]
    elif isinstance(data, str):
        return data.replace('\\n', '\n')
    else:
        return data

async def extract_atomic_facts(transcript: str) -> List[Dict]:
    """
    Extract atomic facts from transcript using the Reframe/FRAME methodology.
    ALWAYS uses Viettel Netmind.
    """
    system_prompt = """You are an expert at breaking down meeting transcripts into atomic facts. Your task is to extract clear, factual statements with proper context and TIMESTAMPS.

IMPORTANT RULES:
1. Output must be a valid JSON list of objects
2. NEVER add information not in the transcript
3. **MANDATORY**: Extract the timestamp `[MM:SS]` appearing before or near the fact.

Input Example:
"[00:15] Speaker A: We need to launch the product by Friday."

Output Example:
[
  {
    "fact": "Speaker A states the product launch deadline is Friday",
    "timestamp": "00:15",
    "citation": "[00:15]"
  }
]

Output Format:
Must return a JSON object with a single key "facts" containing a list of objects:
{
    "facts": [
        {
            "fact": "Clear atomic statement",
            "context": "Immediate context and implications",
            "timestamp": "MM:SS",
            "citation": "[MM:SS]"
        }
    ]
}"""

    user_prompt = f"""
    Break down this transcript chunk into atomic facts with timestamp.
    
    Current chunk:
    {transcript}

    Provide output as a PURE JSON list (no markdown formatting).
    """

    try:
        # FORCE Use Viettel Netmind Configuration
        client = AsyncOpenAI(
            api_key=VIETTEL_API_KEY,
            base_url=VIETTEL_BASE_URL,
            default_headers={"Content-Type": "application/json"}
        )
        
        print(f"🤖 atomic_facts: Calling Viettel Netmind ({VIETTEL_DEFAULT_MODEL})...")
        
        response = await client.chat.completions.create(
            model=VIETTEL_DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_completion_tokens=4096
        )
        content = response.choices[0].message.content

        # DEBUG: Print raw content to see what's wrong
        # print(f"\n🐛 DEBUG: RAW ATOMIC FACTS RESPONSE:\n{content}\n")

        # 1. Enhanced JSON Extraction (Regex)
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # Maybe it's just code block without lang
            code_match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
            if code_match:
                content = code_match.group(1)
        
        content = content.strip()
        
        try:
            parsed_content = json.loads(content)
            
            # 2. Flexible Structure Parsing
            facts = []
            if isinstance(parsed_content, list):
                facts = parsed_content
            elif isinstance(parsed_content, dict):
                 # Search for common keys containing the list
                 found = False
                 for key in ['facts', 'items', 'statements', 'atomic_facts', 'response', 'data']:
                     if key in parsed_content and isinstance(parsed_content[key], list):
                         facts = parsed_content[key]
                         found = True
                         break
                 
                 # If no list found, maybe the dict itself is a single fact?
                 if not found:
                     if "fact" in parsed_content: 
                         facts = [parsed_content]
                     else:
                         # Last resort: look for ANY list in values
                         for v in parsed_content.values():
                             if isinstance(v, list):
                                 facts = v
                                 break
            
            # 3. Validation & Timestamp Normalization
            valid_facts = []
            for f in facts:
                # Handle simple strings
                if isinstance(f, str):
                    valid_facts.append({
                        "fact": f, 
                        "timestamp": "", 
                        "citation": ""
                    })
                    continue
                    
                if isinstance(f, dict):
                    # Get main fact text
                    fact_txt = f.get("fact") or f.get("statement") or f.get("content")
                    if not fact_txt:
                        continue
                     
                    # Filter dummy error messages
                    ft_lower = str(fact_txt).lower()
                    if "no clear" in ft_lower or "error" in ft_lower:
                        continue

                    # Normalize Timestamp & Citation
                    ts = f.get("timestamp", "")
                    cit = f.get("citation", "")
                    
                    # Convert float timestamp to string if needed
                    if isinstance(ts, (int, float)):
                        ts = str(ts) 

                    # Logic: Ensure both exist if one exists
                    if ts and not cit:
                        cit = f"[{ts}]"
                    if cit and not ts:
                        # Extract MM:SS from [MM:SS]
                        ts_match = re.search(r'\[(\d{1,2}:\d{2})\]', cit)
                        if ts_match:
                            ts = ts_match.group(1)
                        else:
                            ts = cit.replace("[", "").replace("]", "")
                        
                    f["fact"] = fact_txt
                    f["timestamp"] = ts
                    f["citation"] = cit
                    
                    valid_facts.append(f)

            if len(valid_facts) == 0:
                 print(f"⚠️ Parsed JSON but found 0 valid facts.")
                 return []
                
            print(f"✅ Extracted {len(valid_facts)} atomic facts")
            return valid_facts
            
        except json.JSONDecodeError:
            print(f"❌ Failed to parse atomic facts JSON. Content: {content[:100]}...")
            return []
            
    except Exception as e:
        print(f"❌ Error extracting atomic facts: {str(e)}")
        # Fallback to returning original text as one fact
        return [{"fact": transcript, "context": "Error extracting facts", "verbose_context": ""}]

async def generate_meeting_minutes(template: dict, system_prompt: str, user_prompt: str, metadata: Optional[Dict[str, Any]] = None) -> SummaryResponse:
    """Generate summary using Viettel Netmind API (Markdown First strategy)"""
    
    print(f"🤖 generate_meeting_minutes: Calling Viettel Netmind ({VIETTEL_DEFAULT_MODEL})...")
    
    try:
        client = AsyncOpenAI(
            api_key=VIETTEL_API_KEY,
            base_url=VIETTEL_BASE_URL,
            default_headers={"Content-Type": "application/json"}
        )
        
        response = await client.chat.completions.create(
            model=VIETTEL_DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3, # Slightly creative but grounded
            max_completion_tokens=4096
        )
        
        generated_text = response.choices[0].message.content
        clean_text = generated_text.strip()
        
        # Cleanup code fences if present
        if clean_text.startswith("```markdown"): clean_text = clean_text[11:]
        if clean_text.startswith("```"): clean_text = clean_text[3:]
        if clean_text.endswith("```"): clean_text = clean_text[:-3]
        
        clean_text = clean_text.strip()
        
        # Try to parse Markdown back to JSON (Sections) for structured storage if possible
        # Simple parser: Split by "## "
        summary_dict = {}
        # current_section = "General" 
        
        # Create legacy summary structure for compatibility
        legacy_summary = {}
        
        # We start with the full markdown
        markdown_output = clean_text
        
        # Generate HTML output
        html_output = markdown_to_html(markdown_output, metadata)
        print("✅ Generated HTML output from markdown")
        
        try:
             # Basic Markdown to Dict parsing for Legacy UI support
             lines = clean_text.split('\n')
             current_key = "Tổng quan"
             buffer = []
             
             for line in lines:
                 if line.strip().startswith("## "):
                     # New section
                     if list(buffer):
                         summary_dict[current_key] = "\n".join(buffer).strip()
                     
                     current_key = line.strip().replace("## ", "").strip()
                     buffer = []
                 else:
                     buffer.append(line)
             
             if list(buffer):
                 summary_dict[current_key] = "\n".join(buffer).strip()
                 
             # Populate legacy_summary based on parsed sections
             for key, content in summary_dict.items():
                 legacy_summary[key] = {
                     "title": key,
                     "blocks": [{"content": content, "type": "paragraph", "id": f"{key}-0"}]
                 }
                 
        except Exception as e:
            print(f"⚠️ Failed to parse markdown back to structure: {e}")
            
        return SummaryResponse(
            summary=legacy_summary,
            markdown=markdown_output, # Primary output
            html=html_output,  # NEW: HTML output
            summary_json=None,
            raw_summary=generated_text,
            model=VIETTEL_DEFAULT_MODEL
        )

    except Exception as e:
        print(f"Viettel API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Viettel API Error: {str(e)}")

# Routes
@router.get("/templates", response_model=List[TemplateInfo])
async def list_templates():
    """List available summary templates"""
    return get_templates()

@router.post("/generate", response_model=SummaryResponse)
async def generate_summary(request: GenerateRequest):
    """Generate summary using Viettel Netmind"""
    
    try:
        # 0. Load Transcript with Timestamps from DB (Primary Source)
        # This overrides the frontend text to ensure we have [MM:SS] format for citations
        transcript_input = request.transcript
        
        if request.meeting_id:
            try:
                conn = sqlite3.connect(get_db_path())
                cursor = conn.cursor()
                
                # Correct Schema: transcripts table stores individual segments as rows
                # Columns: transcript, speaker, audio_start_time
                cursor.execute("""
                    SELECT audio_start_time, speaker, transcript 
                    FROM transcripts 
                    WHERE meeting_id = ? 
                    ORDER BY audio_start_time ASC
                """, (request.meeting_id,))
                
                rows = cursor.fetchall()
                
                if rows:
                    print(f"✅ Loaded {len(rows)} segments from DB for timestamps.")
                    formatted_lines = []
                    for row in rows:
                        start_s = row[0] if row[0] is not None else 0
                        speaker = row[1] if row[1] else "Unknown"
                        text = row[2] if row[2] else ""
                        
                        mm = int(start_s // 60)
                        ss = int(start_s % 60)
                        time_str = f"[{mm:02d}:{ss:02d}]"
                        
                        formatted_lines.append(f"{time_str} {speaker}: {text}")
                    
                    transcript_input = "\n".join(formatted_lines)
                    print("✅ Formatted transcript with timestamps for LLM.")
                else:
                     print("⚠️ No transcript rows found in DB for this meeting_id.")
                
                conn.close()
            except Exception as e:
                print(f"❌ Error loading transcript from DB: {e}")
                # Fallback to request.transcript (which might lack timestamps)

        # 1. Load Template
        template = get_template_content(request.template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template {request.template_id} not found")

        # 2. Extract Atomic Facts (Reframe/FRAME Methodology)
        print(f"\n🚀 STARTING REFRAME PIPELINE...")
        print(f"1️⃣ Extracting Atomic Facts (Groundedness Check)...")
        
        atomic_facts = await extract_atomic_facts(transcript_input)
        
        # Format facts for the generator
        facts_text = json.dumps(atomic_facts, ensure_ascii=False, indent=2)
        print(f"✅ Fact Extraction Complete. Found {len(atomic_facts)} facts.")

        # 3. Construct Improved Prompt (inspired by desktop app's Pydantic approach)
        
        # Metadata Context
        metadata_context = ""
        if request.metadata:
            metadata_context = f"""
THÔNG TIN CUỘC HỌP:
- Tiêu đề: {request.metadata.get('meeting_title', 'Không xác định')}
- Thời gian: {request.metadata.get('date', 'Không xác định')}
- Danh sách tham dự: {', '.join(request.metadata.get('participants', [])) if request.metadata.get('participants') else 'Không xác định'}
"""
        # Build Section Guidelines
        section_guidelines = ""
        for section in template.get("sections", []):
            section_guidelines += f"\n### {section['title']}\n- Yêu cầu: {section['instruction']}\n"

        system_prompt = f"""Bạn là thư ký cuộc họp chuyên nghiệp. Nhiệm vụ: Tạo biên bản họp CHẤT LƯỢNG CAO, CHÍNH XÁC theo cấu trúc yêu cầu.

{metadata_context}

CẤU TRÚC BIÊN BẢN (BẮT BUỘC TUÂN THỦ):
Bạn phải tạo ra báo cáo định dạng MARKDOWN gồm đúng các mục sau đây (theo thứ tự):
{section_guidelines}

QUY TẮC CITATION (BẮT BUỘC - RẤT QUAN TRỌNG):
- Nguồn dữ liệu "Atomic Facts" có trường `citation` hoặc `timestamp`.
- **MỌI THÔNG TIN QUAN TRỌNG** (Quyết định, Con số, Deadline, Chỉ đạo, Lý do) **PHẢI** có citation ở cuối câu.
- Định dạng citation: `[MM:SS]` (Ví dụ: `[12:30]`, `[05:45]`).
- Nếu 1 đoạn văn gồm nhiều ý từ cùng 1 thời điểm, đặt citation ở cuối đoạn.
- **KHÔNG ĐƯỢC BỎ QUA BƯỚC NÀY**.
- Ví dụ đúng:
  - "Doanh thu tháng này đạt 5 tỷ. [10:15]"
  - "Giám đốc yêu cầu nộp báo cáo trước thứ 6 [12:00] và phê bình việc đi muộn [12:05]."

QUY TẮC FORMAT:
1. Dùng Markdown Headers cấp 2 (`## `) cho tên các mục.
2. Dùng Bảng (`|...|`) cho danh sách có nhiều trường thông tin.
3. Dùng Bullet points (`- `) cho các ý liệt kê.
4. KHÔNG dùng json code block. Trả về Markdown Text thuần túy.
"""

        # Prepare input for summary generation
        if atomic_facts and len(atomic_facts) > 0:
            user_prompt_content = f"""SOURCE ATOMIC FACTS (SỬ DỤNG NHỮNG SỰ KIỆN NÀY ĐỂ VIẾT BIÊN BẢN):
---
{facts_text}
---"""
            print("✅ Using ATOMIC FACTS for generation.")
        else:
            print("⚠️ Atomic facts empty. Falling back to RAW TRANSCRIPT.")
            user_prompt_content = f"""SOURCE TRANSCRIPT (SỬ DỤNG NỘI DUNG NÀY ĐỂ VIẾT BIÊN BẢN):
---
{request.transcript}
---"""

        user_prompt = f"""{user_prompt_content}

NGỮ CẢNH BỔ SUNG:
{request.custom_prompt if request.custom_prompt else "Không có"}

Hãy tạo biên bản họp chi tiết bằng định dạng MARKDOWN."""

        # 3. Generate (pass metadata for HTML generation)
        result = await generate_meeting_minutes(template, system_prompt, user_prompt, request.metadata)
        
        # 4. Automatically Save to Database if meeting_id is provided
        if request.meeting_id:
            try:
                print(f"💾 Saving summary to database for meeting: {request.meeting_id}")
                # Prepare payload specifically for storage
                save_payload = {}
                
                # Save Markdown (New Standard for display)
                if result.markdown:
                    save_payload["markdown"] = result.markdown
                
                # Save Legacy Summary (For compatibility)
                if result.summary:
                    save_payload.update(result.summary)
                    
                # Save Raw JSON/Blocks if available
                if result.summary_json:
                    save_payload["summary_json"] = result.summary_json
                
                json_str = json.dumps(save_payload, ensure_ascii=False)
                
                # Get HTML content
                html_content = result.html if result.html else ""
                
                conn = sqlite3.connect(get_db_path())
                cursor = conn.cursor()
                cursor.execute("UPDATE meetings SET summary = ?, html_summary = ? WHERE id = ?", (json_str, html_content, request.meeting_id))
                
                if cursor.rowcount == 0:
                    print(f"⚠️ Warning: Meeting ID {request.meeting_id} not found in DB.")
                else:
                    conn.commit()
                    print(f"✅ Summary SAVED to Database successfully.")
                    
                conn.close()
                
            except Exception as e:
                print(f"❌ Failed to save summary to DB: {e}")
                import traceback
                traceback.print_exc()

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in generate_summary: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
