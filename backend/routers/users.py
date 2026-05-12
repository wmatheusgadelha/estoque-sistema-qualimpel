from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..core.database import get_db
from ..core.security import get_current_user, require_admin, get_password_hash
from ..models.models import EstoqueUser
from ..schemas.schemas import UserCreate, UserUpdate, UserOut

router = APIRouter(prefix="/api/users", tags=["Usuários"])

@router.get("/", response_model=List[UserOut], summary="Listar usuários")
def list_users(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(EstoqueUser).order_by(EstoqueUser.nome).all()

@router.post("/", response_model=UserOut, summary="Cadastrar usuário")
def create_user(data: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(EstoqueUser).filter(EstoqueUser.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    user = EstoqueUser(
        nome=data.nome, email=data.email,
        hashed_password=get_password_hash(data.password),
        role=data.role, cargo=data.cargo,
        telefone=data.telefone, matricula=data.matricula
    )
    db.add(user); db.commit(); db.refresh(user)
    return user

@router.put("/{user_id}", response_model=UserOut, summary="Editar usuário")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(EstoqueUser).filter(EstoqueUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit(); db.refresh(user)
    return user

@router.delete("/{user_id}", summary="Desativar usuário")
def deactivate_user(user_id: int, db: Session = Depends(get_db), current_user: EstoqueUser = Depends(require_admin)):
    user = db.query(EstoqueUser).filter(EstoqueUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode desativar a si mesmo")
    user.is_active = False
    db.commit()
    return {"message": "Usuário desativado"}
