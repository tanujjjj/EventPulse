from fastapi_users import schemas
import uuid

class UserRead(schemas.BaseUser[uuid.UUID]):
    username: str
    full_name: str | None

class UserCreate(schemas.BaseUserCreate):
    username: str
    full_name: str | None

class UserUpdate(schemas.BaseUserUpdate):
    username: str
    full_name: str | None
