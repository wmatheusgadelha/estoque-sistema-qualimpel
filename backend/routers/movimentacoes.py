from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.models import Movimentacao, Item, Lote, Familia

router = APIRouter(prefix="/api/movimentacoes", tags=["Movimentações"])

@router.get("/", summary="Extrato de movimentações")
def list_movimentacoes(
    item_id: Optional[int] = Query(None),
    tipo: Optional[str] = Query(None),
    familia_id: Optional[int] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    q = db.query(Movimentacao).order_by(Movimentacao.created_at.desc())
    if item_id:
        q = q.filter(Movimentacao.item_id == item_id)
    if tipo:
        q = q.filter(Movimentacao.tipo == tipo)
    if familia_id:
        q = q.filter(Movimentacao.familia_id == familia_id)
    if data_inicio:
        q = q.filter(Movimentacao.created_at >= data_inicio)
    if data_fim:
        from datetime import datetime, time
        q = q.filter(Movimentacao.created_at <= datetime.combine(data_fim, time.max))

    movs = q.limit(limit).all()
    result = []
    for m in movs:
        item = db.query(Item).filter(Item.id == m.item_id).first()
        lote = db.query(Lote).filter(Lote.id == m.lote_id).first() if m.lote_id else None
        familia = db.query(Familia).filter(Familia.id == m.familia_id).first() if m.familia_id else None
        result.append({
            "id": m.id, "tipo": m.tipo,
            "item_id": m.item_id,
            "item_nome": item.nome if item else None,
            "item_codigo": item.codigo if item else None,
            "item_tipo": item.tipo if item else None,
            "lote_id": m.lote_id,
            "lote_codigo": lote.codigo_lote if lote else None,
            "familia_id": m.familia_id,
            "familia_nome": familia.nome if familia else None,
            "quantidade": m.quantidade,
            "saldo_apos": m.saldo_apos,
            "observacoes": m.observacoes,
            "created_at": m.created_at
        })
    return result
