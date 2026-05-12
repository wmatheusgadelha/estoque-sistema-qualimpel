from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..core.database import get_db
from ..core.security import get_current_user, require_gestor_or_admin
from ..models.models import Familia
from ..schemas.schemas import FamiliaCreate, FamiliaUpdate, FamiliaOut

router = APIRouter(prefix="/api/familias", tags=["Famílias"])

@router.get("/", response_model=List[FamiliaOut], summary="Listar famílias")
def list_familias(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Familia).filter(Familia.is_active == True).order_by(Familia.nome).all()

@router.post("/", response_model=FamiliaOut, summary="Cadastrar família")
def create_familia(data: FamiliaCreate, db: Session = Depends(get_db), _=Depends(require_gestor_or_admin)):
    if db.query(Familia).filter(Familia.nome == data.nome).first():
        raise HTTPException(status_code=400, detail="Família já cadastrada")
    f = Familia(**data.model_dump())
    db.add(f); db.commit(); db.refresh(f)
    return f

@router.put("/{fid}", response_model=FamiliaOut, summary="Editar família")
def update_familia(fid: int, data: FamiliaUpdate, db: Session = Depends(get_db), _=Depends(require_gestor_or_admin)):
    f = db.query(Familia).filter(Familia.id == fid).first()
    if not f:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(f, k, v)
    db.commit(); db.refresh(f)
    return f

@router.delete("/{fid}", summary="Excluir família")
def delete_familia(fid: int, db: Session = Depends(get_db), _=Depends(require_gestor_or_admin)):
    f = db.query(Familia).filter(Familia.id == fid).first()
    if not f:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    f.is_active = False
    db.commit()
    return {"message": "Família desativada"}
