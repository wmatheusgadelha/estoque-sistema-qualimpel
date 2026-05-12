from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import verify_password, get_password_hash, create_access_token, get_current_user
from ..models.models import EstoqueUser
from ..schemas.schemas import Token, ChangePassword

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])

@router.post("/token", response_model=Token, summary="Login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(EstoqueUser).filter(
        EstoqueUser.email == form_data.username,
        EstoqueUser.is_active == True
    ).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "nome": user.nome, "email": user.email, "role": user.role}
    }

@router.post("/change-password", summary="Trocar senha")
def change_password(data: ChangePassword, db: Session = Depends(get_db), current_user: EstoqueUser = Depends(get_current_user)):
    if not verify_password(data.senha_atual, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    current_user.hashed_password = get_password_hash(data.nova_senha)
    db.commit()
    return {"message": "Senha alterada com sucesso"}
