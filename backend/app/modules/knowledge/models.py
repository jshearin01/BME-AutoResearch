import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.shared.db import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, index=True, default="")
    text = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
