from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.models import Item, Lote, EntradaNF, LancamentoProducao, Movimentacao

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats", summary="KPIs do Dashboard")
def get_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    hoje = date.today()
    mes_atual = hoje.replace(day=1)

    # Contagem de itens ativos por tipo
    tipos = {}
    for tipo in ["MP", "EMB", "PI", "PA"]:
        tipos[tipo] = db.query(Item).filter(Item.tipo == tipo, Item.is_active == True).count()

    # Itens com estoque baixo ou zerado
    itens_ativos = db.query(Item).filter(Item.is_active == True).all()
    itens_baixo = 0
    itens_zerado = 0
    for item in itens_ativos:
        saldo = db.query(func.sum(Lote.quantidade_atual)).filter(
            Lote.item_id == item.id, Lote.is_active == True
        ).scalar() or 0
        if saldo <= 0:
            itens_zerado += 1
        elif item.estoque_minimo > 0 and saldo <= item.estoque_minimo:
            itens_baixo += 1

    # Entradas do mês
    entradas_mes = db.query(EntradaNF).filter(EntradaNF.data_entrada >= mes_atual).count()

    # Produções do mês
    producoes_mes = db.query(LancamentoProducao).filter(LancamentoProducao.data_producao >= mes_atual).count()

    # Movimentações de hoje
    mov_hoje = db.query(Movimentacao).filter(
        func.date(Movimentacao.created_at) == hoje
    ).count()

    # Top 5 MP com estoque mais baixo vs mínimo
    alertas = []
    for item in itens_ativos:
        if item.tipo in ("MP", "EMB") and item.estoque_minimo > 0:
            saldo = db.query(func.sum(Lote.quantidade_atual)).filter(
                Lote.item_id == item.id, Lote.is_active == True
            ).scalar() or 0
            if saldo <= item.estoque_minimo:
                pct = (saldo / item.estoque_minimo * 100) if item.estoque_minimo else 0
                alertas.append({
                    "item_id": item.id, "nome": item.nome, "tipo": item.tipo,
                    "estoque_atual": round(float(saldo), 2),
                    "estoque_minimo": item.estoque_minimo,
                    "percentual": round(pct, 1), "unidade": item.unidade
                })
    alertas.sort(key=lambda x: x["percentual"])

    # Resumo por tipo com estoque
    resumo_tipos = []
    for tipo in ["MP", "EMB", "PI", "PA"]:
        itens_tipo = db.query(Item).filter(Item.tipo == tipo, Item.is_active == True).all()
        total_itens = len(itens_tipo)
        ok = sum(1 for i in itens_tipo if (
            db.query(func.sum(Lote.quantidade_atual)).filter(Lote.item_id == i.id, Lote.is_active == True).scalar() or 0
        ) > (i.estoque_minimo or 0))
        resumo_tipos.append({
            "tipo": tipo, "total": total_itens,
            "ok": ok, "alerta": total_itens - ok
        })

    return {
        "total_mp": tipos["MP"],
        "total_emb": tipos["EMB"],
        "total_pi": tipos["PI"],
        "total_pa": tipos["PA"],
        "itens_estoque_baixo": itens_baixo,
        "itens_estoque_zerado": itens_zerado,
        "entradas_mes": entradas_mes,
        "producoes_mes": producoes_mes,
        "movimentacoes_hoje": mov_hoje,
        "alertas_estoque": alertas[:10],
        "resumo_tipos": resumo_tipos
    }
