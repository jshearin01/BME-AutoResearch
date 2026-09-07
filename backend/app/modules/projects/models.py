import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime
from app.shared.db import Base


def new_id(prefix: str = "proj") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    problem = Column(Text, default="")
    users = Column(Text, default="")
    constraints = Column(Text, default="")
    stage = Column(String, default="problem")  # problem|evidence|design|cad|print|done
    spec_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
