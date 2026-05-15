import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text

router = APIRouter()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Initialize engine globally
engine = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL)
    except Exception as e:
        print(f"Ext Router: Failed to connect to database: {e}")

class TagRequest(BaseModel):
    chat_id: str
    user_id: str
    data_function: str
    exam: str = "General"
    subject: str = "General"
    topic: str = "General"
    lesson: str = "General"
    concept: str = "General"
    level: str = ""
    number: str = ""

@router.post("/history/tag")
async def tag_chat(req: TagRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    query = text("""
        INSERT INTO ext_chat_tags (
            chat_id, user_id, data_function,
            exam, subject, topic, lesson, concept,
            level, number
        )
        VALUES (
            :chat_id, :user_id, :data_function,
            :exam, :subject, :topic, :lesson, :concept,
            :level, :number
        )
        ON CONFLICT (chat_id) DO UPDATE SET
            data_function = EXCLUDED.data_function,
            exam = EXCLUDED.exam,
            subject = EXCLUDED.subject,
            topic = EXCLUDED.topic,
            lesson = EXCLUDED.lesson,
            concept = EXCLUDED.concept,
            level = EXCLUDED.level,
            number = EXCLUDED.number
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, {
                "chat_id": req.chat_id,
                "user_id": req.user_id,
                "data_function": req.data_function,
                "exam": req.exam,
                "subject": req.subject,
                "topic": req.topic,
                "lesson": req.lesson,
                "concept": req.concept,
                "level": req.level or "",
                "number": req.number or "",
            })
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/tags/{user_id}")
async def get_tags(user_id: str):
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    # COALESCE so legacy rows (NULL level/number) return '' to the frontend,
    # making client-side identity comparisons null-safe.
    query = text("""
        SELECT
            chat_id,
            data_function,
            exam,
            subject,
            topic,
            lesson,
            concept,
            COALESCE(level, '')  AS level,
            COALESCE(number, '') AS number,
            created_at
        FROM ext_chat_tags
        WHERE user_id = :user_id
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"user_id": user_id})
            tags = [dict(row._mapping) for row in result]
            return {"tags": tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

