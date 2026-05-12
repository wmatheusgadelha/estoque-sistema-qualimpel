from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date
from ..core.database import get_db
from ..core.security import get_current_user, require_gestor_or_admin
from ..models.models import (
    LancamentoProducao, LancamentoProducaoConsumo, ReceitaItem,
    Item, Lote, Movimentacao, Familia
)
from ..schemas.schemas import LancamentoProducaoCreate, LancamentoProducaoPreview

router = APIRouter(prefix="/api/producao", tags=["Produção"])

def _get_saldo(db, item_id):
    r = db.query(func.sum(Lote.quantidade_atual)).filter(
        Lote.item_id == item_id, Lote.is_active == True
    ).scalar()
    return float(r or 0)

def _get_lotes_fifo(db, item_id, quantidade_necessaria):
    """Retorna lista de (lote, quantidade_a_consumir) em ordem FIFO."""
    lotes = db.query(Lote).filter(
        Lote.item_id == item_id,
        Lote.is_active == True,
        Lote.quantidade_atual > 0
    ).order_by(Lote.data_entrada).all()

    resultado = []
    restante = quantidade_necessaria
    for lote in lotes:
        if restante <= 0:
            break
        consumir = min(lote.quantidade_atual, restante)
        resultado.append((lote, consumir))
        restante -= consumir
    return resultado, restante  # restante > 0 significa estoque insuficiente

@router.get("/preview", summary="Preview de consumo para uma produção")
def preview_producao(
    item_id: int,
    quantidade: float,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    if item.tipo not in ("PI", "PA"):
        raise HTTPException(status_code=400, detail="Somente PI ou PA podem ser produzidos")

    receita = db.query(ReceitaItem).filter(ReceitaItem.item_pai_id == item_id).all()
    if not receita:
        raise HTTPException(status_code=400, detail="Este item não possui receita cadastrada")

    consumo_preview = []
    pode_produzir = True

    for r in receita:
        filho = db.query(Item).filter(Item.id == r.item_filho_id).first()
        if not filho:
            continue
        qtd_necessaria = r.quantidade * quantidade
        estoque_atual = _get_saldo(db, r.item_filho_id)
        saldo_apos = estoque_atual - qtd_necessaria
        suficiente = saldo_apos >= 0

        if not suficiente:
            pode_produzir = False

        lotes_fifo, _ = _get_lotes_fifo(db, r.item_filho_id, qtd_necessaria)
        lotes_info = [
            {"lote_id": l.id, "codigo_lote": l.codigo_lote,
             "quantidade_atual": l.quantidade_atual, "a_consumir": c}
            for l, c in lotes_fifo
        ]

        consumo_preview.append({
            "item_id": filho.id, "item_nome": filho.nome, "item_codigo": filho.codigo,
            "item_tipo": filho.tipo, "unidade": r.unidade or filho.unidade,
            "quantidade_necessaria": round(qtd_necessaria, 6),
            "estoque_atual": round(estoque_atual, 4),
            "saldo_apos": round(saldo_apos, 4),
            "suficiente": suficiente,
            "lotes_disponiveis": lotes_info
        })

    return {
        "item_id": item.id, "item_nome": item.nome, "item_tipo": item.tipo,
        "quantidade": quantidade, "consumo": consumo_preview,
        "pode_produzir": pode_produzir
    }

@router.post("/", summary="Registrar produção de PI ou PA")
def registrar_producao(
    data: LancamentoProducaoCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    item = db.query(Item).filter(Item.id == data.item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    if item.tipo not in ("PI", "PA"):
        raise HTTPException(status_code=400, detail="Somente PI ou PA podem ser produzidos")

    receita = db.query(ReceitaItem).filter(ReceitaItem.item_pai_id == data.item_id).all()
    if not receita:
        raise HTTPException(status_code=400, detail="Este item não possui receita cadastrada")

    # Constrói mapa de consumo manual (override por item_id)
    consumo_override = {}
    if data.consumo_manual:
        for c in data.consumo_manual:
            consumo_override[c.item_id] = c

    # Valida e prepara consumo
    consumos_planejados = []  # lista de dict com item, lote, qtd
    for r in receita:
        filho = db.query(Item).filter(Item.id == r.item_filho_id).first()
        if not filho:
            raise HTTPException(status_code=400, detail=f"Componente ID {r.item_filho_id} não encontrado")

        qtd_necessaria = r.quantidade * data.quantidade

        if r.item_filho_id in consumo_override:
            # Consumo manual com lote específico
            c = consumo_override[r.item_filho_id]
            lote = db.query(Lote).filter(Lote.id == c.lote_id).first() if c.lote_id else None
            if lote and lote.quantidade_atual < qtd_necessaria:
                raise HTTPException(
                    status_code=400,
                    detail=f"Lote {lote.codigo_lote} insuficiente para {filho.nome}"
                )
            consumos_planejados.append({
                "item": filho, "lote": lote,
                "qtd": qtd_necessaria, "receita_item": r
            })
        else:
            # FIFO automático
            lotes_fifo, restante = _get_lotes_fifo(db, r.item_filho_id, qtd_necessaria)
            if restante > 0.001:  # tolerância de 1g
                raise HTTPException(
                    status_code=400,
                    detail=f"Estoque insuficiente para {filho.nome}: faltam {round(restante, 4)} {filho.unidade}"
                )
            for lote, consumir in lotes_fifo:
                consumos_planejados.append({
                    "item": filho, "lote": lote,
                    "qtd": consumir, "receita_item": r
                })

    # Gera lote do item produzido
    lote_codigo = data.lote_codigo
    if not lote_codigo:
        tipo_prefix = "PI" if item.tipo == "PI" else "PA"
        lote_codigo = f"{tipo_prefix}-{item.codigo}-{data.data_producao.strftime('%d%m%y')}-{data.turno or 'T1'}"

    lote_produzido = Lote(
        codigo_lote=lote_codigo, item_id=data.item_id,
        familia_id=data.familia_id or item.familia_id,
        quantidade_inicial=data.quantidade, quantidade_atual=data.quantidade,
        data_entrada=data.data_producao
    )
    db.add(lote_produzido); db.commit(); db.refresh(lote_produzido)

    # Cria lançamento
    lancamento = LancamentoProducao(
        item_id=data.item_id, familia_id=data.familia_id or item.familia_id,
        quantidade=data.quantidade, lote_gerado_id=lote_produzido.id,
        data_producao=data.data_producao, turno=data.turno,
        observacoes=data.observacoes, usuario_id=current_user.id
    )
    db.add(lancamento); db.commit(); db.refresh(lancamento)

    # Executa consumo
    for c in consumos_planejados:
        # Debita lote
        if c["lote"]:
            c["lote"].quantidade_atual -= c["qtd"]
            if c["lote"].quantidade_atual <= 0:
                c["lote"].is_active = False

        # Registro de consumo
        consumo_rec = LancamentoProducaoConsumo(
            lancamento_id=lancamento.id, item_id=c["item"].id,
            lote_id=c["lote"].id if c["lote"] else None,
            quantidade=c["qtd"]
        )
        db.add(consumo_rec)

        # Movimentação de saída do componente
        saldo = _get_saldo(db, c["item"].id) - c["qtd"]
        mov_saida = Movimentacao(
            tipo=f"PRODUCAO_{item.tipo}", item_id=c["item"].id,
            lote_id=c["lote"].id if c["lote"] else None,
            familia_id=data.familia_id, quantidade=-c["qtd"],
            saldo_apos=max(0, saldo),
            referencia_id=lancamento.id, referencia_tipo="lancamento_producao",
            observacoes=f"Produção {item.tipo}: {item.nome} x{data.quantidade}",
            usuario_id=current_user.id
        )
        db.add(mov_saida)

    # Movimentação de entrada do item produzido
    saldo_produzido = _get_saldo(db, data.item_id) + data.quantidade
    mov_entrada = Movimentacao(
        tipo=f"PRODUCAO_{item.tipo}", item_id=data.item_id,
        lote_id=lote_produzido.id, familia_id=data.familia_id,
        quantidade=data.quantidade, saldo_apos=saldo_produzido,
        referencia_id=lancamento.id, referencia_tipo="lancamento_producao",
        observacoes=f"Produção de {item.tipo}: {item.nome} - Turno {data.turno or 'N/I'}",
        usuario_id=current_user.id
    )
    db.add(mov_entrada)
    db.commit()

    return {"message": f"{item.tipo} registrado com sucesso", "lancamento_id": lancamento.id, "lote_gerado": lote_codigo}

@router.get("/", summary="Listar lançamentos de produção")
def list_lancamentos(
    tipo: Optional[str] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    item_id: Optional[int] = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    q = db.query(LancamentoProducao).order_by(LancamentoProducao.data_producao.desc(), LancamentoProducao.id.desc())
    if item_id:
        q = q.filter(LancamentoProducao.item_id == item_id)
    if data_inicio:
        q = q.filter(LancamentoProducao.data_producao >= data_inicio)
    if data_fim:
        q = q.filter(LancamentoProducao.data_producao <= data_fim)
    lancamentos = q.limit(limit).all()

    result = []
    for l in lancamentos:
        item = db.query(Item).filter(Item.id == l.item_id).first()
        if tipo and item and item.tipo != tipo:
            continue
        familia = db.query(Familia).filter(Familia.id == l.familia_id).first() if l.familia_id else None
        consumos = db.query(LancamentoProducaoConsumo).filter(LancamentoProducaoConsumo.lancamento_id == l.id).all()
        consumos_out = []
        for c in consumos:
            ci = db.query(Item).filter(Item.id == c.item_id).first()
            cl = db.query(Lote).filter(Lote.id == c.lote_id).first() if c.lote_id else None
            consumos_out.append({
                "item_id": c.item_id, "item_nome": ci.nome if ci else None,
                "item_tipo": ci.tipo if ci else None,
                "lote_codigo": cl.codigo_lote if cl else None,
                "quantidade": c.quantidade
            })
        result.append({
            "id": l.id, "item_id": l.item_id,
            "item_nome": item.nome if item else None,
            "item_tipo": item.tipo if item else None,
            "familia_nome": familia.nome if familia else None,
            "quantidade": l.quantidade, "data_producao": l.data_producao,
            "turno": l.turno, "observacoes": l.observacoes,
            "lote_gerado_id": l.lote_gerado_id,
            "consumos": consumos_out, "created_at": l.created_at
        })
    return result

@router.delete("/{lancamento_id}", summary="Estornar lançamento de produção")
def delete_lancamento(lancamento_id: int, db: Session = Depends(get_db), _=Depends(require_gestor_or_admin)):
    lanc = db.query(LancamentoProducao).filter(LancamentoProducao.id == lancamento_id).first()
    if not lanc:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    item = db.query(Item).filter(Item.id == lanc.item_id).first()

    # Estorna lote produzido
    lote_prod = db.query(Lote).filter(Lote.id == lanc.lote_gerado_id).first()
    if lote_prod:
        lote_prod.quantidade_atual -= lanc.quantidade
        if lote_prod.quantidade_atual <= 0:
            lote_prod.is_active = False

    # Restaura componentes consumidos
    consumos = db.query(LancamentoProducaoConsumo).filter(LancamentoProducaoConsumo.lancamento_id == lancamento_id).all()
    for c in consumos:
        lote = db.query(Lote).filter(Lote.id == c.lote_id).first() if c.lote_id else None
        if lote:
            lote.quantidade_atual += c.quantidade
            lote.is_active = True

    db.delete(lanc)
    db.commit()
    return {"message": "Lançamento estornado com sucesso"}
