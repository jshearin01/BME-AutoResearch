import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.shared.db import Base


class RunLog(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, index=True, default="global")
    agent = Column(String, default="")
    action = Column(String, default="")
    input_summary = Column(Text, default="")
    output_summary = Column(Text, default="")
    status = Column(String, default="ok")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
