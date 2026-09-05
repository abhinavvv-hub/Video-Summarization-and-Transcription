import os
import subprocess
import shutil
import riva.client
from ollama import Client
from dotenv import load_dotenv
import json
import re
import traceback

load_dotenv()

try:
    CANARY_API_KEY = os.environ["CANARY_API_KEY"]
    OLLAMA_API_KEY = os.environ["OLLAMA_API_KEY"]
except KeyError as e:
    raise RuntimeError(f"Missing environment variable: {e}. Add it to your .env file.")
CHUNK_DIR = "audio_chunks"
CHUNK_DURATION = 180
SERVER = "grpc.nvcf.nvidia.com:443"
FUNCTION_ID = "b0e8b4a5-217c-40b7-9b96-17d84e666317"
OLLAMA_MODEL = "gpt-oss:120b"

ollama_client = Client(
    host="https://ollama.com",
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"}
)

def transcribe_video(video_path, transcript_path="transcript.txt"):
    """Extract audio, chunk it, and transcribe using NVIDIA Canary"""
    
    print(f"Starting transcription for: {video_path}")
    if os.path.exists(CHUNK_DIR):
        shutil.rmtree(CHUNK_DIR)
    os.makedirs(CHUNK_DIR)
    
    chunk_pattern = os.path.join(CHUNK_DIR, "chunk_%03d.wav")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vn", "-ac", "1", "-ar", "16000",
                "-sample_fmt", "s16", "-f", "segment",
                "-segment_time", str(CHUNK_DURATION),
                "-reset_timestamps", "1", chunk_pattern,
            ],
            check=True,
            capture_output=True
        )
        print("Audio extraction completed")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e}")
        print(f"FFmpeg stderr: {e.stderr.decode() if e.stderr else 'No stderr'}")
        raise
    
    chunks = sorted(
        os.path.join(CHUNK_DIR, file)
        for file in os.listdir(CHUNK_DIR)
        if file.endswith(".wav")
    )
    
    print(f"Created {len(chunks)} audio chunks")
    
    if len(chunks) == 0:
        raise Exception("No audio chunks were created")
    
    print("Connecting to NVIDIA Canary...")
    auth = riva.client.Auth(
        uri=SERVER,
        use_ssl=True,
        metadata_args=[
            ("authorization", f"Bearer {CANARY_API_KEY}"),
            ("function-id", FUNCTION_ID),
        ],
    )
    asr_service = riva.client.ASRService(auth)
    print("Connected to Canary")
    
    config = riva.client.RecognitionConfig(
        encoding=riva.client.AudioEncoding.LINEAR_PCM,
        sample_rate_hertz=16000,
        language_code="en-US",
        max_alternatives=1,
        enable_automatic_punctuation=True,
    )
    
    all_transcripts = []
    for i, chunk_file in enumerate(chunks):
        print(f"Transcribing chunk {i+1}/{len(chunks)}")
        try:
            with open(chunk_file, "rb") as f:
                audio_data = f.read()
            
            print(f"Audio data size: {len(audio_data)} bytes")
            response = asr_service.offline_recognize(audio_data, config)
            chunk_text = ""
            
            for result in response.results:
                if result.alternatives:
                    chunk_text += result.alternatives[0].transcript + " "
            
            chunk_text = chunk_text.strip()
            if chunk_text:
                all_transcripts.append(chunk_text)
                print(f"Chunk {i+1} transcribed: {len(chunk_text)} characters")
            else:
                print(f"No speech detected in chunk {i+1}")
                
        except Exception as e:
            print(f"Error processing chunk {i+1}: {e}")
            traceback.print_exc()
            continue
    
    if os.path.exists(CHUNK_DIR):
        shutil.rmtree(CHUNK_DIR)
        print("Cleaned up audio chunks")
    
    transcript_contents = "\n".join(all_transcripts)
    
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(transcript_contents)
    
    print(f"Transcription complete: {len(transcript_contents)} characters")
    return transcript_contents

def extract_content_from_response(response):
    """Extract text content from various response formats"""
    
    print(f"Response type: {type(response)}")
    
    if isinstance(response, str):
        return response
    
    if isinstance(response, dict):
        print(f"Response keys: {list(response.keys())}")
        
        if 'message' in response:
            msg = response['message']
            if isinstance(msg, dict):
                if 'content' in msg:
                    return msg['content']
                else:
                    return str(msg)
            else:
                return str(msg)
        elif 'content' in response:
            return response['content']
        elif 'response' in response:
            return response['response']
        elif 'text' in response:
            return response['text']
        else:
            print(f"Unknown dict format: {json.dumps(response, indent=2)[:1000]}")
            return str(response)
    
    try:
        if hasattr(response, 'message'):
            if hasattr(response.message, 'content'):
                return response.message.content
            elif isinstance(response.message, dict) and 'content' in response.message:
                return response.message['content']
            else:
                return str(response.message)
        elif hasattr(response, 'content'):
            return response.content
        elif hasattr(response, 'response'):
            return response.response
        elif hasattr(response, 'text'):
            return response.text
    except Exception as e:
        print(f"Error extracting from object: {e}")
    
    return str(response)

def parse_analysis_response(analysis_text):
    """Parse the analysis response into structured format"""
    
    try:
        parsed_json = json.loads(analysis_text)
        return parsed_json
    except:
        pass
    
    start_idx = analysis_text.find('{')
    end_idx = analysis_text.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = analysis_text[start_idx:end_idx + 1]
        try:
            return json.loads(json_str)
        except:
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            json_str = json_str.replace('\n', ' ').replace('\r', '')
            try:
                return json.loads(json_str)
            except:
                pass
    
    result = {
        "overview": "",
        "key_takeaways": [],
        "important_points": [],
        "actionable_advice": [],
        "final_summary": ""
    }
    
    lines = analysis_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if 'OVERVIEW' in line.upper() or 'HIGH-LEVEL' in line.upper():
            current_section = 'overview'
            continue
        elif 'TAKEAWAY' in line.upper():
            current_section = 'key_takeaways'
            continue
        elif 'IMPORTANT POINT' in line.upper() or 'MAJOR TOPIC' in line.upper():
            current_section = 'important_points'
            continue
        elif 'ACTIONABLE' in line.upper() or 'ADVICE' in line.upper():
            current_section = 'actionable_advice'
            continue
        elif 'FINAL SUMMARY' in line.upper() or ('SUMMARY' in line.upper() and current_section != 'overview'):
            current_section = 'final_summary'
            continue
        
        if re.match(r'^\d+\.', line) and any(
            word in line.upper() for word in ['OVERVIEW', 'TAKEAWAY', 'POINT', 'ADVICE', 'SUMMARY']
        ):
            continue
        
        if current_section == 'overview':
            result['overview'] += line + ' '
        elif current_section == 'key_takeaways':
            if line.startswith('-') or line.startswith('•') or line.startswith('*') or re.match(r'^\d+\.', line):
                clean_line = re.sub(r'^[\d\.\-\•\*\s]+', '', line).strip()
                if clean_line:
                    result['key_takeaways'].append(clean_line)
        elif current_section == 'important_points':
            if line.startswith('-') or line.startswith('•') or line.startswith('*') or re.match(r'^\d+\.', line):
                clean_line = re.sub(r'^[\d\.\-\•\*\s]+', '', line).strip()
                if ':' in clean_line:
                    topic, details = clean_line.split(':', 1)
                    result['important_points'].append({
                        "topic": topic.strip(),
                        "details": details.strip()
                    })
                elif clean_line:
                    result['important_points'].append({
                        "topic": clean_line,
                        "details": ""
                    })
        elif current_section == 'actionable_advice':
            if line.startswith('-') or line.startswith('•') or line.startswith('*') or re.match(r'^\d+\.', line):
                clean_line = re.sub(r'^[\d\.\-\•\*\s]+', '', line).strip()
                if clean_line:
                    result['actionable_advice'].append(clean_line)
        elif current_section == 'final_summary':
            result['final_summary'] += line + ' '
    
    result['overview'] = result['overview'].strip()
    result['final_summary'] = result['final_summary'].strip()
    
    if not any([result['overview'], result['key_takeaways'], 
                result['important_points'], result['actionable_advice'], 
                result['final_summary']]):
        result['final_summary'] = analysis_text.strip()
    
    return result

def summarize_transcript(transcript_text):
    """Generate structured summary using Ollama"""
    
    if not transcript_text.strip():
        return {"error": "Transcript is empty"}
    
    prompt = f"""
Analyze the following video transcript and provide a structured summary.

Please format your response EXACTLY as follows:

1. HIGH-LEVEL OVERVIEW
[2-3 sentences overview]

2. KEY TAKEAWAYS
- [takeaway 1]
- [takeaway 2]
- [takeaway 3]

3. IMPORTANT POINTS
- [Topic]: [explanation]
- [Topic]: [explanation]
- [Topic]: [explanation]

4. ACTIONABLE ADVICE
- [advice 1]
- [advice 2]

5. FINAL SUMMARY
[concise paragraph summary]

VIDEO TRANSCRIPT:
--------------------------------------------------
{transcript_text[:50000]}
--------------------------------------------------
"""
    
    try:
        print("Sending to Ollama for summarization...")
        
        try:
            response = ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            print("Chat API successful")
        except Exception as chat_error:
            print(f"Chat API failed: {chat_error}")
            try:
                response = ollama_client.generate(
                    model=OLLAMA_MODEL,
                    prompt=prompt,
                )
                print("Generate API successful")
            except Exception as gen_error:
                print(f"Generate API also failed: {gen_error}")
                raise
        
        analysis_text = extract_content_from_response(response)
        
        print(f"Analysis text length: {len(analysis_text)}")
        print("Raw response (first 500 chars):")
        print(analysis_text[:500])
        print("...")
        
        summary = parse_analysis_response(analysis_text)
        
        default_summary = {
            "overview": "No overview available",
            "key_takeaways": [],
            "important_points": [],
            "actionable_advice": [],
            "final_summary": "No summary available"
        }
        
        for key in default_summary:
            if key not in summary or not summary[key]:
                summary[key] = default_summary[key]
        
        print("Parsed summary successfully")
        print(f"Overview: {summary['overview'][:100]}...")
        print(f"Number of takeaways: {len(summary['key_takeaways'])}")
        print(f"Number of important points: {len(summary['important_points'])}")
        print(f"Number of advice items: {len(summary['actionable_advice'])}")
        
        return summary
            
    except Exception as e:
        print(f"Summarization error: {e}")
        traceback.print_exc()
        return {
            "overview": "Unable to generate overview",
            "key_takeaways": [],
            "important_points": [],
            "actionable_advice": [],
            "final_summary": f"Error during summarization: {str(e)}"
        }

if __name__ == "__main__":
    VIDEO_FILE = "sample_data/videoplayback.mp4"
    TRANSCRIPT_FILE = "transcript.txt"
    
    print("=" * 60)
    print("STEP 1: Extracting and chunking audio")
    print("=" * 60)
    
    transcript = transcribe_video(VIDEO_FILE, TRANSCRIPT_FILE)
    
    print("\n" + "=" * 60)
    print("STEP 2: Analyzing transcript with Ollama Cloud")
    print("=" * 60)
    
    summary = summarize_transcript(transcript)
    print("\nFinal Summary:")
    print(json.dumps(summary, indent=2))
