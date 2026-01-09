from fastapi import APIRouter
from fastapi import Depends

from app.deps import get_user_service
from app.models.schemas import UserCreateRequest, UserResponse

# create user
router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse)
async def create_user_api(
        user_create_request: UserCreateRequest,
        user_service=Depends(get_user_service)
):
    user = user_service.create_user(name=user_create_request.name, email=user_create_request.email)
    return UserResponse(
        id=user.get('id'),
        name=user.get('name'),
        email=user.get('email'),
        created_at=user.get('created_at')
    )
