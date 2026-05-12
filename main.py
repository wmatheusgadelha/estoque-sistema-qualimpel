from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from backend.core.database import engine, Base, SessionLocal
from backend.core.security import get_password_hash
from backend.core.config import settings
from backend.models.models import (
    EstoqueUser, Familia, Item, ReceitaItem, Lote, EntradaNF, EntradaNFItem,
    LancamentoProducao, LancamentoProducaoConsumo, Movimentacao
)
from backend.routers import auth, users, familias, itens, entradas, producao, movimentacoes, dashboard

from datetime import date

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if settings.RESET_SEED:
            # Limpa dados demo
            for model in [Movimentacao, LancamentoProducaoConsumo, LancamentoProducao,
                          EntradaNFItem, EntradaNF, Lote, ReceitaItem, Item, Familia, EstoqueUser]:
                db.query(model).delete()
            db.commit()

        # Seed apenas se banco vazio
        if db.query(EstoqueUser).count() == 0:
            _seed(db)
    finally:
        db.close()
    yield

def _seed(db):
    # Admin
    admin = EstoqueUser(
        nome="Administrador", email="admin@estoque.com",
        hashed_password=get_password_hash("admin123"),
        role="admin", cargo="Administrador do Sistema"
    )
    gestor = EstoqueUser(
        nome="Gestor de Estoque", email="gestor@estoque.com",
        hashed_password=get_password_hash("gestor123"),
        role="gestor", cargo="Gestor de Estoque"
    )
    operador = EstoqueUser(
        nome="Operador Logística", email="logistica@estoque.com",
        hashed_password=get_password_hash("logistica123"),
        role="tecnico", cargo="Operador de Logística"
    )
    db.add_all([admin, gestor, operador]); db.commit()

    # Famílias
    qualimpel = Familia(nome="Qualimpel", descricao="Materiais próprios Qualimpel", cor="#3B82F6")
    casa_km = Familia(nome="Casa KM", descricao="Materiais do cliente Casa KM", cor="#10B981")
    amacitel = Familia(nome="Amacitel", descricao="Materiais do cliente Amacitel", cor="#F59E0B")
    db.add_all([qualimpel, casa_km, amacitel]); db.commit()

    # Matérias-Primas (MP)
    sal_qualimpel = Item(codigo="8010761", nome="SAL REFINADO S/ IODO", tipo="MP", unidade="Kg",
                        familia_id=qualimpel.id, estoque_minimo=300000)
    sal_km = Item(codigo="8010761-KM", nome="SAL REFINADO S/ IODO - CASA KM", tipo="MP", unidade="Kg",
                 familia_id=casa_km.id, estoque_minimo=50000)
    acido = Item(codigo="8010016", nome="ACIDO SULFONICO (LAS) 96", tipo="MP", unidade="Kg",
                familia_id=qualimpel.id, estoque_minimo=2500)
    barrilha_leve = Item(codigo="8010750", nome="BARRILHA LEVE", tipo="MP", unidade="Kg",
                        familia_id=qualimpel.id, estoque_minimo=25000)
    barrilha_densa = Item(codigo="8010515", nome="CARBONATO DE SODIO DENSO (BARRILHA DENSA)", tipo="MP",
                         unidade="Kg", familia_id=qualimpel.id, estoque_minimo=50000)
    blend_enz = Item(codigo="8010667", nome="BLEND ENZIMATICO", tipo="MP", unidade="Kg",
                    familia_id=qualimpel.id, estoque_minimo=1000)
    azul = Item(codigo="8010767", nome="AZUL DISPERCROM ASB", tipo="MP", unidade="Kg",
               familia_id=qualimpel.id, estoque_minimo=1000)
    fragrancia = Item(codigo="8010760", nome="FRAGRANCIA AMOR IN BLUE DET 2", tipo="MP", unidade="Kg",
                     familia_id=qualimpel.id, estoque_minimo=1000)
    perfume = Item(codigo="8010768", nome="ALL YOU NEED IS LOVE MOD SYM", tipo="MP", unidade="Kg",
                  familia_id=qualimpel.id, estoque_minimo=1000)
    db.add_all([sal_qualimpel, sal_km, acido, barrilha_leve, barrilha_densa,
                blend_enz, azul, fragrancia, perfume]); db.commit()

    # Embalagens / Insumos (EMB)
    etiqueta = Item(codigo="EMB001", nome="ETIQUETA AUTO ADESIVA SATO 100 X 50MM", tipo="EMB",
                   unidade="UND", familia_id=qualimpel.id, estoque_minimo=300000)
    palete = Item(codigo="EMB002", nome="PALETE DE MADEIRA PADRÃO PBR", tipo="EMB",
                 unidade="UND", familia_id=qualimpel.id, estoque_minimo=300)
    filme_stretch = Item(codigo="EMB003", nome="FILME STRETCH MANUAL", tipo="EMB",
                        unidade="Kg", familia_id=qualimpel.id, estoque_minimo=1000)
    filme_enfard_860 = Item(codigo="EMB004", nome="FILME ENFARD 860MM", tipo="EMB",
                           unidade="Kg", familia_id=qualimpel.id, estoque_minimo=2000)
    filme_enfard_1030 = Item(codigo="EMB005", nome="FILME ENFARD 1030MM", tipo="EMB",
                            unidade="Kg", familia_id=qualimpel.id, estoque_minimo=2000)
    filme_enfard_1170 = Item(codigo="EMB006", nome="FILME ENFARD 1170MM", tipo="EMB",
                            unidade="Kg", familia_id=qualimpel.id, estoque_minimo=2000)
    # Bags por cliente
    bag_q800 = Item(codigo="BAG-Q800", nome="FILME BAG QUALIMP 800G", tipo="EMB",
                   unidade="Kg", familia_id=qualimpel.id, estoque_minimo=750)
    bag_q16 = Item(codigo="BAG-Q16", nome="FILME BAG QUALIMP 1,6KG", tipo="EMB",
                  unidade="Kg", familia_id=qualimpel.id, estoque_minimo=750)
    bag_q4 = Item(codigo="BAG-Q4", nome="FILME BAG QUALIMP 4KG", tipo="EMB",
                 unidade="Kg", familia_id=qualimpel.id, estoque_minimo=750)
    bag_atp400 = Item(codigo="BAG-ATP400", nome="FILME BAG LAVA ROUPAS AMACITEL TOQUE DE POESIA 400G",
                     tipo="EMB", unidade="Kg", familia_id=amacitel.id, estoque_minimo=1500)
    bag_atp800 = Item(codigo="BAG-ATP800", nome="FILME BAG LAVA ROUPAS AMACITEL TOQUE DE POESIA 800G",
                     tipo="EMB", unidade="Kg", familia_id=amacitel.id, estoque_minimo=1500)
    bag_atp16 = Item(codigo="BAG-ATP16", nome="FILME BAG LAVA ROUPAS AMACITEL TOQUE DE POESIA 1,6KG",
                    tipo="EMB", unidade="Kg", familia_id=amacitel.id, estoque_minimo=1500)
    bag_atp24 = Item(codigo="BAG-ATP24", nome="FILME BAG LAVA ROUPAS AMACITEL TOQUE DE POESIA 2,4KG",
                    tipo="EMB", unidade="Kg", familia_id=amacitel.id, estoque_minimo=1500)
    bag_atp4 = Item(codigo="BAG-ATP4", nome="FILME BAG LAVA ROUPAS AMACITEL TOQUE DE POESIA 4KG",
                   tipo="EMB", unidade="Kg", familia_id=amacitel.id, estoque_minimo=1500)
    db.add_all([etiqueta, palete, filme_stretch, filme_enfard_860, filme_enfard_1030, filme_enfard_1170,
                bag_q800, bag_q16, bag_q4, bag_atp400, bag_atp800, bag_atp16, bag_atp24, bag_atp4])
    db.commit()

    # Produto Intermediário (PI)
    pi_po = Item(codigo="8028689", nome="PI PO BASE LAVA ROUPAS PO", tipo="PI", unidade="Kg",
                familia_id=casa_km.id, estoque_minimo=150000)
    db.add(pi_po); db.commit()

    # Receita do PI
    receita_pi = [
        ReceitaItem(item_pai_id=pi_po.id, item_filho_id=barrilha_densa.id, quantidade=0.4535, unidade="Kg"),
        ReceitaItem(item_pai_id=pi_po.id, item_filho_id=blend_enz.id, quantidade=0.005, unidade="Kg"),
    ]
    db.add_all(receita_pi); db.commit()

    # Produtos Acabados (PA) - exemplos
    pa_atp16 = Item(codigo="208733", nome="SABÃO EM PÓ - AMACITEL T.P 1,6KG", tipo="PA",
                   unidade="FARDO", familia_id=amacitel.id, estoque_minimo=0)
    pa_atp24 = Item(codigo="109795", nome="SABÃO EM PÓ - AMACITEL T.P 2,4KG", tipo="PA",
                   unidade="FARDO", familia_id=amacitel.id, estoque_minimo=0)
    pa_q16 = Item(codigo="Q16", nome="SABÃO EM PÓ - QUALIMP 1,6KG", tipo="PA",
                 unidade="FARDO", familia_id=qualimpel.id, estoque_minimo=0)
    db.add_all([pa_atp16, pa_atp24, pa_q16]); db.commit()

    # Receita PA Amacitel TP 1,6kg (por FARDO)
    for item_pai_id, componentes in [
        (pa_atp16.id, [
            (filme_stretch.id, 0.011111), (bag_atp16.id, 0.098),
            (etiqueta.id, 1.013889), (sal_qualimpel.id, 6.46653),
            (azul.id, 0.001162), (fragrancia.id, 0.02324),
            (palete.id, 0.01388), (filme_enfard_1030.id, 0.06),
            (barrilha_densa.id, 1.6268), (blend_enz.id, 0.01743),
            (pi_po.id, 3.486),
        ]),
        (pa_atp24.id, [
            (filme_stretch.id, 0.011111), (bag_atp24.id, 0.119),
            (etiqueta.id, 1.013889), (sal_qualimpel.id, 9.6296),
            (azul.id, 0.00173), (fragrancia.id, 0.034608),
            (palete.id, 0.01388), (filme_enfard_1030.id, 0.06),
            (barrilha_densa.id, 2.42256), (blend_enz.id, 0.025956),
            (pi_po.id, 5.1912),
        ]),
        (pa_q16.id, [
            (filme_stretch.id, 0.014286), (bag_q16.id, 0.144),
            (etiqueta.id, 1.017858), (acido.id, 0.4),
            (sal_qualimpel.id, 17.335), (azul.id, 0.00147),
            (perfume.id, 0.02988), (palete.id, 0.017858),
            (filme_enfard_1030.id, 0.06), (barrilha_densa.id, 2.153),
        ]),
    ]:
        for filho_id, qtd in componentes:
            db.add(ReceitaItem(item_pai_id=item_pai_id, item_filho_id=filho_id, quantidade=qtd))
    db.commit()

    # Lotes iniciais de estoque (saldo atual da planilha)
    lotes_iniciais = [
        (sal_qualimpel.id, qualimpel.id, "LOTE-INICIAL-SAL-Q", 200000),
        (acido.id, qualimpel.id, "LOTE-INICIAL-ACIDO", 250),
        (barrilha_densa.id, qualimpel.id, "LOTE-INICIAL-BARRILHA-D", 51100),
        (barrilha_leve.id, qualimpel.id, "LOTE-INICIAL-BARRILHA-L", 75000),
        (blend_enz.id, qualimpel.id, "LOTE-INICIAL-BLEND", 4800),
        (azul.id, qualimpel.id, "LOTE-INICIAL-AZUL", 284.5),
        (fragrancia.id, qualimpel.id, "LOTE-INICIAL-FRAG", 1546.5),
        (perfume.id, qualimpel.id, "LOTE-INICIAL-PERF", 1810.3),
        (etiqueta.id, qualimpel.id, "LOTE-INICIAL-ETQ", 325156),
        (palete.id, qualimpel.id, "LOTE-INICIAL-PAL", 309),
        (filme_stretch.id, qualimpel.id, "LOTE-INICIAL-STRETCH", 1987.2),
        (filme_enfard_860.id, qualimpel.id, "LOTE-INICIAL-ENF860", 4600.84),
        (filme_enfard_1030.id, qualimpel.id, "LOTE-INICIAL-ENF1030", 2208.26),
        (filme_enfard_1170.id, qualimpel.id, "LOTE-INICIAL-ENF1170", 6914.48),
        (bag_q800.id, qualimpel.id, "LOTE-INICIAL-BQ800", 1519),
        (bag_q16.id, qualimpel.id, "LOTE-INICIAL-BQ16", 820.976),
        (bag_q4.id, qualimpel.id, "LOTE-INICIAL-BQ4", 600),
        (bag_atp400.id, amacitel.id, "LOTE-INICIAL-ATP400", 3920.85),
        (bag_atp800.id, amacitel.id, "LOTE-INICIAL-ATP800", 6973),
        (bag_atp16.id, amacitel.id, "LOTE-INICIAL-ATP16", 2160),
        (bag_atp24.id, amacitel.id, "LOTE-INICIAL-ATP24", 3105),
        (bag_atp4.id, amacitel.id, "LOTE-INICIAL-ATP4", 4975),
        (pi_po.id, casa_km.id, "LOTE-INICIAL-PI-PO", 60300),
    ]
    for item_id, familia_id, codigo_lote, qtd in lotes_iniciais:
        l = Lote(codigo_lote=codigo_lote, item_id=item_id, familia_id=familia_id,
                quantidade_inicial=qtd, quantidade_atual=qtd,
                data_entrada=date(2025, 4, 1))
        db.add(l)
    db.commit()


app = FastAPI(
    title="Qualimpel — Sistema de Estoque",
    description="Módulo de Gestão de Estoque: MP, EMB, PI e PA com controle por lote e família.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(familias.router)
app.include_router(itens.router)
app.include_router(entradas.router)
app.include_router(producao.router)
app.include_router(movimentacoes.router)
app.include_router(dashboard.router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse("frontend/index.html")

@app.get("/health")
def health():
    return {"status": "ok", "service": "estoque-sistema"}
