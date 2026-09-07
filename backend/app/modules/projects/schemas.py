from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    problem: str = ""
    users: str = ""
    constraints: str = ""


class ProjectUpdate(BaseModel):
    title: str | None = None
    problem: str | None = None
    users: str | None = None
    constraints: str | None = None
    stage: str | None = None
    spec_json: str | None = None


class ProjectOut(BaseModel):
    id: str
    title: str
    problem: str
    users: str
    constraints: str
    stage: str
    spec_json: str

    class Config:
        from_attributes = True
