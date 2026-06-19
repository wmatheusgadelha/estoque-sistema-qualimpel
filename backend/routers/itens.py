from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date
from ..core.database import get_db
from ..core.security import get_current_user, require_gestor_or_admin
from ..models.models import Item, ReceitaItem, Lote, Familia, Movimentacao
from ..schemas.schemas import ItemCreate, ItemUpdate, ItemOut, ReceitaItemOut

router = APIRouter(prefix="/api/itens", tags=["Itens de Estoque"])

def _estoque_atual(db: Session, item_id: int) -> float:
    result = db.query(func.sum(Lote.quantidade_atual)).filter(
        Lote.item_id == item_id, Lote.is_active == True
    ).scalar()
    return float(result or 0)

def _build_item_out(item: Item, db: Session, with_receita: bool = False) -> dict:
    estoque = _estoque_atual(db, item.id)
    familia = db.query(Familia).filter(Familia.id == item.familia_id).first() if item.familia_id else None
    status = "OK"
    if estoque <= 0:
        status = "ZERADO"
    elif item.estoque_minimo > 0 and estoque <= item.estoque_minimo:
        status = "BAIXO"

    data = {
        "id": item.id, "codigo": item.codigo, "nome": item.nome,
        "tipo": item.tipo, "unidade": item.unidade,
        "familia_id": item.familia_id,
        "familia_nome": familia.nome if familia else None,
        "familia_cor": familia.cor if familia else None,
        "estoque_minimo": item.estoque_minimo,
        "estoque_atual": estoque,
        "status_estoque": status,
        "observacoes": item.observacoes,
        "is_active": item.is_active,
    }
    if with_receita:
        receita_rows = db.query(ReceitaItem).filter(ReceitaItem.item_pai_id == item.id).all()
        receita = []
        for r in receita_rows:
            filho = db.query(Item).filter(Item.id == r.item_filho_id).first()
            receita.append({
                "id": r.id, "item_filho_id": r.item_filho_id,
                "quantidade": r.quantidade, "unidade": r.unidade,
                "observacoes": r.observacoes,
                "item_filho_nome": filho.nome if filho else None,
                "item_filho_codigo": filho.codigo if filho else None,
                "item_filho_tipo": filho.tipo if filho else None,
                "item_filho_unidade": filho.unidade if filho else None,
            })
        data["receita"] = receita
    return data

@router.get("/", summary="Listar itens")
def list_itens(
    tipo: Optional[str] = Query(None),
    familia_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    apenas_ativos: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    q = db.query(Item)
    if apenas_ativos:
        q = q.filter(Item.is_active == True)
    if tipo:
        q = q.filter(Item.tipo == tipo)
    if familia_id:
        q = q.filter(Item.familia_id == familia_id)
    if search:
        q = q.filter(Item.nome.ilike(f"%{search}%") | Item.codigo.ilike(f"%{search}%"))
    itens = q.order_by(Item.nome).all()
    return [_build_item_out(i, db) for i in itens]

@router.get("/{item_id}", summary="Detalhe do item com receita")
def get_item(item_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    return _build_item_out(item, db, with_receita=True)

@router.post("/", summary="Cadastrar item")
def create_item(data: ItemCreate, db: Session = Depends(get_db), _=Depends(require_gestor_or_admin)):
    if db.query(Item).filter(Item.codigo == data.codigo).first():
        raise HTTPException(status_code=400, detail="Código já cadastrado")
    item = Item(
        codigo=data.codigo, nome=data.nome, tipo=data.tipo,
        unidade=data.unidade, familia_id=data.familia_id,
        estoque_minimo=data.estoque_minimo, observacoes=data.observacoes
    )
    db.add(item); db.commit(); db.refresh(item)

    if data.receita and item.tipo in ("PI", "PA"):
        for r in data.receita:
            receita_item = ReceitaItem(
                item_pai_id=item.id, item_filho_id=r.item_filho_id,
                quantidade=r.quantidade, unidade=r.unidade, observacoes=r.observacoes
            )
            db.add(receita_item)
        db.commit()
    return _build_item_out(item, db, with_receita=True)

@router.put("/{item_id}", summary="Editar item")
def update_item(item_id: int, data: ItemUpdate, db: Session = Depends(get_db), _=Depends(require_gestor_or_admin)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    campos = data.model_dump(exclude_unset=True, exclude={"receita"})
    for k, v in campos.items():
        setattr(item, k, v)

    if data.receita is not None:
        db.query(ReceitaItem).filter(ReceitaItem.item_pai_id == item_id).delete()
        for r in data.receita:
            receita_item = ReceitaItem(
                item_pai_id=item_id, item_filho_id=r.item_filho_id,
                quantidade=r.quantidade, unidade=r.unidade, observacoes=r.observacoes
            )
            db.add(receita_item)
    db.commit(); db.refresh(item)
    return _build_item_out(item, db, with_receita=True)

@router.delete("/{item_id}", summary="Desativar item")
def delete_item(item_id: int, db: Session = Depends(get_db), _=Depends(require_gestor_or_admin)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    item.is_active = False
    db.commit()
    return {"message": "Item desativado"}

@router.get("/{item_id}/lotes", summary="Lotes disponíveis do item")
def get_lotes_item(item_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    lotes = db.query(Lote).filter(
        Lote.item_id == item_id,
        Lote.is_active == True,
        Lote.quantidade_atual > 0
    ).order_by(Lote.data_entrada).all()
    result = []
    for l in lotes:
        familia = db.query(Familia).filter(Familia.id == l.familia_id).first() if l.familia_id else None
        result.append({
            "id": l.id, "codigo_lote": l.codigo_lote,
            "quantidade_atual": l.quantidade_atual,
            "data_entrada": l.data_entrada, "validade": l.validade,
            "familia_nome": familia.nome if familia else None,
        })
    return result

@router.post("/{item_id}/ajuste", summary="Ajuste de saldo / inventário")
def ajuste_saldo(
    item_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    nova_quantidade = float(data.get("nova_quantidade", 0))
    lote_id = data.get("lote_id")
    observacoes = data.get("observacoes", "Ajuste de inventário")

    saldo_atual = float(db.query(func.sum(Lote.quantidade_atual)).filter(
        Lote.item_id == item_id, Lote.is_active == True
    ).scalar() or 0)

    diferenca = nova_quantidade - saldo_atual
    lote_usado_id = None

    if lote_id:
        lote = db.query(Lote).filter(Lote.id == lote_id, Lote.item_id == item_id).first()
        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado")
        novo_saldo_lote = lote.quantidade_atual + diferenca
        if novo_saldo_lote < 0:
            raise HTTPException(status_code=400, detail="Ajuste deixaria o lote com saldo negativo")
        lote.quantidade_atual = novo_saldo_lote
        lote.is_active = novo_saldo_lote > 0
        lote_usado_id = lote.id
    else:
        if abs(diferenca) < 0.001:
            return {"message": "Nenhuma diferença a ajustar", "diferenca": 0}
        if diferenca > 0:
            codigo_lote = f"AJUSTE-{item.codigo}-{date.today().strftime('%d%m%y')}"
            lote_existente = db.query(Lote).filter(
                Lote.codigo_lote == codigo_lote, Lote.item_id == item_id
            ).first()
            if lote_existente:
                lote_existente.quantidade_atual += diferenca
                lote_existente.quantidade_inicial += diferenca
                lote_existente.is_active = True
                lote_usado_id = lote_existente.id
            else:
                novo_lote = Lote(
                    codigo_lote=codigo_lote, item_id=item_id,
                    familia_id=item.familia_id,
                    quantidade_inicial=diferenca, quantidade_atual=diferenca,
                    data_entrada=date.today()
                )
                db.add(novo_lote); db.commit(); db.refresh(novo_lote)
                lote_usado_id = novo_lote.id
        else:
            lotes = db.query(Lote).filter(
                Lote.item_id == item_id, Lote.is_active == True, Lote.quantidade_atual > 0
            ).order_by(Lote.data_entrada).all()
            restante = abs(diferenca)
            if lotes:
                lote_usado_id = lotes[0].id
            for lote in lotes:
                if restante <= 0.001:
                    break
                consumir = min(lote.quantidade_atual, restante)
                lote.quantidade_atual -= consumir
                if lote.quantidade_atual <= 0:
                    lote.is_active = False
                restante -= consumir
            if restante > 0.001:
                raise HTTPException(
                    status_code=400,
                    detail=f"Estoque insuficiente para reduzir {abs(diferenca):.3f} {item.unidade}"
                )

    mov = Movimentacao(
        tipo="AJUSTE", item_id=item_id, lote_id=lote_usado_id,
        familia_id=item.familia_id, quantidade=round(diferenca, 6),
        saldo_apos=round(nova_quantidade, 6),
        observacoes=f"AJUSTE: {observacoes}",
        usuario_id=current_user.id
    )
    db.add(mov)
    db.commit()

    return {
        "message": "Saldo ajustado com sucesso",
        "saldo_anterior": round(saldo_atual, 4),
        "nova_quantidade": round(nova_quantidade, 4),
        "diferenca": round(diferenca, 4)
    }
