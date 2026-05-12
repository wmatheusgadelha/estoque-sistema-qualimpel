from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date
from ..core.database import get_db
from ..core.security import get_current_user, require_gestor_or_admin
from ..models.models import EntradaNF, EntradaNFItem, Lote, Movimentacao, Item, Familia
from ..schemas.schemas import EntradaNFCreate, EntradaNFOut

router = APIRouter(prefix="/api/entradas", tags=["Entradas de NF"])

def _get_saldo(db, item_id):
    r = db.query(func.sum(Lote.quantidade_atual)).filter(Lote.item_id == item_id, Lote.is_active == True).scalar()
    return float(r or 0)

@router.get("/", summary="Listar entradas de NF")
def list_entradas(
    search: Optional[str] = Query(None),
    familia_id: Optional[int] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    q = db.query(EntradaNF).order_by(EntradaNF.data_entrada.desc(), EntradaNF.id.desc())
    if search:
        q = q.filter(EntradaNF.numero_nf.ilike(f"%{search}%") | EntradaNF.fornecedor.ilike(f"%{search}%"))
    if familia_id:
        q = q.filter(EntradaNF.familia_id == familia_id)
    if data_inicio:
        q = q.filter(EntradaNF.data_entrada >= data_inicio)
    if data_fim:
        q = q.filter(EntradaNF.data_entrada <= data_fim)
    entradas = q.limit(limit).all()
    result = []
    for e in entradas:
        familia = db.query(Familia).filter(Familia.id == e.familia_id).first() if e.familia_id else None
        itens = db.query(EntradaNFItem).filter(EntradaNFItem.entrada_nf_id == e.id).all()
        itens_out = []
        for i in itens:
            item = db.query(Item).filter(Item.id == i.item_id).first()
            itens_out.append({
                "id": i.id, "item_id": i.item_id,
                "item_nome": item.nome if item else None,
                "item_codigo": item.codigo if item else None,
                "quantidade": i.quantidade, "lote_codigo": i.lote_codigo,
                "lote_id": i.lote_id, "validade": i.validade, "observacoes": i.observacoes
            })
        result.append({
            "id": e.id, "numero_nf": e.numero_nf, "fornecedor": e.fornecedor,
            "data_entrada": e.data_entrada, "familia_id": e.familia_id,
            "familia_nome": familia.nome if familia else None,
            "observacoes": e.observacoes, "itens": itens_out,
            "created_at": e.created_at
        })
    return result

@router.get("/{entrada_id}", summary="Detalhe de uma entrada NF")
def get_entrada(entrada_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    e = db.query(EntradaNF).filter(EntradaNF.id == entrada_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    familia = db.query(Familia).filter(Familia.id == e.familia_id).first() if e.familia_id else None
    itens = db.query(EntradaNFItem).filter(EntradaNFItem.entrada_nf_id == e.id).all()
    itens_out = []
    for i in itens:
        item = db.query(Item).filter(Item.id == i.item_id).first()
        itens_out.append({
            "id": i.id, "item_id": i.item_id,
            "item_nome": item.nome if item else None,
            "item_codigo": item.codigo if item else None,
            "quantidade": i.quantidade, "lote_codigo": i.lote_codigo,
            "lote_id": i.lote_id, "validade": i.validade, "observacoes": i.observacoes
        })
    return {
        "id": e.id, "numero_nf": e.numero_nf, "fornecedor": e.fornecedor,
        "data_entrada": e.data_entrada, "familia_id": e.familia_id,
        "familia_nome": familia.nome if familia else None,
        "observacoes": e.observacoes, "itens": itens_out,
        "created_at": e.created_at
    }

@router.post("/", summary="Registrar entrada de NF")
def create_entrada(data: EntradaNFCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Valida itens
    for item_data in data.itens:
        item = db.query(Item).filter(Item.id == item_data.item_id, Item.is_active == True).first()
        if not item:
            raise HTTPException(status_code=400, detail=f"Item ID {item_data.item_id} não encontrado")
        if item.tipo not in ("MP", "EMB"):
            raise HTTPException(status_code=400, detail=f"Só é possível dar entrada em MP ou EMB. '{item.nome}' é {item.tipo}")

    # Cria a NF
    nf = EntradaNF(
        numero_nf=data.numero_nf, fornecedor=data.fornecedor,
        data_entrada=data.data_entrada, familia_id=data.familia_id,
        observacoes=data.observacoes, conferido_por=current_user.id
    )
    db.add(nf); db.commit(); db.refresh(nf)

    for item_data in data.itens:
        item = db.query(Item).filter(Item.id == item_data.item_id).first()

        # Gera código de lote automático se não informado
        lote_codigo = item_data.lote_codigo
        if not lote_codigo:
            lote_codigo = f"NF{data.numero_nf}-{item.codigo}-{data.data_entrada.strftime('%d%m%y')}"

        # Verifica se lote já existe para este item
        lote_existente = db.query(Lote).filter(
            Lote.codigo_lote == lote_codigo,
            Lote.item_id == item_data.item_id
        ).first()

        if lote_existente:
            # Adiciona ao lote existente
            lote_existente.quantidade_atual += item_data.quantidade
            lote_existente.quantidade_inicial += item_data.quantidade
            lote_id = lote_existente.id
        else:
            # Cria novo lote
            lote = Lote(
                codigo_lote=lote_codigo, item_id=item_data.item_id,
                familia_id=data.familia_id or item.familia_id,
                quantidade_inicial=item_data.quantidade,
                quantidade_atual=item_data.quantidade,
                data_entrada=data.data_entrada,
                validade=item_data.validade
            )
            db.add(lote); db.commit(); db.refresh(lote)
            lote_id = lote.id

        # Item da NF
        nf_item = EntradaNFItem(
            entrada_nf_id=nf.id, item_id=item_data.item_id,
            lote_id=lote_id, quantidade=item_data.quantidade,
            lote_codigo=lote_codigo, validade=item_data.validade,
            observacoes=item_data.observacoes
        )
        db.add(nf_item)

        # Movimentação
        saldo_apos = _get_saldo(db, item_data.item_id) + item_data.quantidade
        mov = Movimentacao(
            tipo="ENTRADA_NF", item_id=item_data.item_id, lote_id=lote_id,
            familia_id=data.familia_id, quantidade=item_data.quantidade,
            saldo_apos=saldo_apos, referencia_id=nf.id,
            referencia_tipo="entrada_nf",
            observacoes=f"NF {data.numero_nf} - {data.fornecedor}",
            usuario_id=current_user.id
        )
        db.add(mov)

    db.commit()
    return {"message": "Entrada registrada com sucesso", "id": nf.id}

@router.delete("/{entrada_id}", summary="Estornar entrada de NF")
def delete_entrada(entrada_id: int, db: Session = Depends(get_db), _=Depends(require_gestor_or_admin)):
    """Estorna uma entrada: reverte os lotes e cria movimentações de estorno."""
    nf = db.query(EntradaNF).filter(EntradaNF.id == entrada_id).first()
    if not nf:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")

    itens_nf = db.query(EntradaNFItem).filter(EntradaNFItem.entrada_nf_id == entrada_id).all()
    for i in itens_nf:
        lote = db.query(Lote).filter(Lote.id == i.lote_id).first()
        if lote:
            if lote.quantidade_atual < i.quantidade:
                raise HTTPException(status_code=400, detail=f"Não é possível estornar: lote {lote.codigo_lote} já foi consumido parcialmente além do permitido")
            lote.quantidade_atual -= i.quantidade
            if lote.quantidade_atual <= 0:
                lote.is_active = False

        saldo_apos = _get_saldo(db, i.item_id) - i.quantidade
        mov = Movimentacao(
            tipo="SAIDA_MANUAL", item_id=i.item_id, lote_id=i.lote_id,
            quantidade=-i.quantidade, saldo_apos=max(0, saldo_apos),
            referencia_id=entrada_id, referencia_tipo="estorno_nf",
            observacoes=f"ESTORNO NF {nf.numero_nf}"
        )
        db.add(mov)

    db.delete(nf)
    db.commit()
    return {"message": "Entrada estornada com sucesso"}
