from typing import Annotated

from fastapi import Depends

from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.auth.service import AuthService


def require_admin(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AuthUser:
    return AuthService.authorize(user, {"admin"})


AdminUser = Annotated[AuthUser, Depends(require_admin)]
