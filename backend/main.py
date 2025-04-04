from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import google.generativeai as genai
import pdfplumber  
import docx  
from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# ✅ Configure Gemini API Key
GEMINI_API_KEY = "AIzaSyBhHBsrcG4WZxKaGFlwif4ckHJpqmIDGfo"
if not GEMINI_API_KEY:
    raise RuntimeError("❌ ERROR: GEMINI_API_KEY is not set!")

genai.configure(api_key=GEMINI_API_KEY)
try:
    model = genai.GenerativeModel("gemini-1.5-pro")
    print("✅ Gemini API configured successfully.")
except Exception as e:
    raise RuntimeError(f"❌ ERROR: Failed to configure Gemini API - {str(e)}")

# ✅ Initialize FastAPI app
app = FastAPI()

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Set up SQLite database
DATABASE_URL = "sqlite:///./chat_history.db"

Base = declarative_base()

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    message = Column(Text)
    response = Column(Text)
    user_conditions = Column(Text)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

# ✅ Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ Function to extract text from uploaded files
def extract_text_from_pdf(file: UploadFile):
    try:
        with pdfplumber.open(file.file) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from PDF: {str(e)}")

def extract_text_from_docx(file: UploadFile):
    try:
        doc = docx.Document(file.file)
        text = "\n".join(para.text for para in doc.paragraphs)
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from DOCX: {str(e)}")

# ✅ Store user chat sessions
user_sessions = {}

# ✅ Request schema
class ChatRequest(BaseModel):
    user_id: str
    message: str
    user_conditions: List[str] = []

@app.post("/chat/")
async def chat(
    user_id: str = Form(...),  
    message: str = Form(...),   
    user_conditions: List[str] = Form([]),  
    file: UploadFile = File(None),  
    db: Session = Depends(get_db),
):
    """Handles user chat interactions with Gemini AI and stores chat history."""
    print(f"📩 Received request: user_id={user_id}, message={message}, conditions={user_conditions}")

    try:
        # ✅ Retrieve past chat history (last 5 messages)
        past_chats = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).order_by(ChatHistory.id.desc()).limit(5).all()
        history = []
        for chat in past_chats[::-1]:
            history.append({"role": "user", "parts": [chat.message]})
            history.append({"role": "model", "parts": [chat.response]})

        # ✅ Initialize session with history
        if user_id not in user_sessions:
            print(f"🆕 Creating new session for {user_id}")
            user_sessions[user_id] = model.start_chat(history=history)

        chat_session = user_sessions[user_id]

        # ✅ Extract text if file is uploaded
        if file:
            if file.filename.endswith(".pdf"):
                report_text = extract_text_from_pdf(file)
            elif file.filename.endswith(".docx"):
                report_text = extract_text_from_docx(file)
            else:
                raise HTTPException(status_code=400, detail="❌ Unsupported file format! Please upload a PDF or DOCX file.")
            
            condition_text = f"User has the following health conditions based on the report: {report_text} "
        else:
            condition_text = f"User has {', '.join(user_conditions)}. " if user_conditions else ""
        
        # ✅ Prepare prompt
        prompt = condition_text + message
        print(f"🚀 Sending prompt: {prompt}")

        # ✅ Send message to AI
        response = chat_session.send_message(prompt)

        if not hasattr(response, "text"):
            raise HTTPException(status_code=500, detail="❌ ERROR: Invalid AI response.")

        # ✅ Save chat to database
        chat_log = ChatHistory(
            user_id=user_id,
            message=message,
            response=response.text.strip(),
            user_conditions=", ".join(user_conditions)
        )
        db.add(chat_log)
        db.commit()

        return {"response": response.text.strip()}

    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"❌ Unexpected error: {str(e)}")

@app.get("/chat/history/")
async def get_chat_history(user_id: str, db: Session = Depends(get_db)):
    """Fetches past chat history for a given user."""
    chats = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).order_by(ChatHistory.id.asc()).all()

    history = []
    for chat in chats:
        history.append({"sender": "user", "text": chat.message, "timestamp": chat.id})
        history.append({"sender": "bot", "text": chat.response, "timestamp": chat.id})

    return {"history": history}

# ✅ Run using: uvicorn main:app --reload
