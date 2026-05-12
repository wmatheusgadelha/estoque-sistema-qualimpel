from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from ..core.database import Base
import enum

# ─── USERS ───────────────────────────────────────────────────────────────────

class EstoqueUser(Base):
    __tablename__ = "estoque_users"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(500), nullable=False)
    role = Column(String(20), default="tecnico")  # admin / gestor / tecnico
    cargo = Column(String(100))
    telefone = Column(String(30))
    matricula = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ─── FAMÍLIA (proprietário do material) ──────────────────────────────────────

class Familia(Base):
    """Família/Proprietário: Qualimpel, Casa KM, Amacitel, etc."""
    __tablename__ = "est_familias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)
    descricao = Column(Text)
    cor = Column(String(7), default="#3B82F6")  # hex color para o badge
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ─── ITEM DE ESTOQUE (MP, EMB, PI, PA) ───────────────────────────────────────

class TipoItem(str, enum.Enum):
    MP = "MP"       # Matéria-Prima
    EMB = "EMB"     # Embalagem/Insumo
    PI = "PI"       # Produto Intermediário
    PA = "PA"       # Produto Acabado

class Item(Base):
    """Cadastro mestre de todos os itens do estoque"""
    __tablename__ = "est_itens"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False)
    nome = Column(String(300), nullable=False)
    tipo = Column(String(10), nullable=False)   # MP / EMB / PI / PA
    unidade = Column(String(20), default="Kg")  # Kg, L, UND, FARDO, etc.
    familia_id = Column(Integer, nullable=True)  # sem FK cross-module
    estoque_minimo = Column(Float, default=0.0)
    observacoes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ─── RECEITA (composição de PI e PA) ─────────────────────────────────────────

class ReceitaItem(Base):
    """Composição/receita: para cada unidade do item_pai, usa X do item_filho"""
    __tablename__ = "est_receitas"

    id = Column(Integer, primary_key=True, index=True)
    item_pai_id = Column(Integer, nullable=False)   # PI ou PA
    item_filho_id = Column(Integer, nullable=False)  # MP, EMB ou PI
    quantidade = Column(Float, nullable=False)       # quantidade por unidade do pai
    unidade = Column(String(20))
    observacoes = Column(Text)

# ─── LOTE ─────────────────────────────────────────────────────────────────────

class Lote(Base):
    """Lote de um item — criado a cada entrada ou produção"""
    __tablename__ = "est_lotes"

    id = Column(Integer, primary_key=True, index=True)
    codigo_lote = Column(String(100), nullable=False)
    item_id = Column(Integer, nullable=False)
    familia_id = Column(Integer, nullable=True)
    quantidade_inicial = Column(Float, nullable=False)
    quantidade_atual = Column(Float, nullable=False)
    data_entrada = Column(Date, nullable=False)
    validade = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)  # False quando zerado
    created_at = Column(DateTime, default=datetime.utcnow)

# ─── ENTRADA DE NOTA FISCAL ───────────────────────────────────────────────────

class EntradaNF(Base):
    """Entrada de materiais via Nota Fiscal"""
    __tablename__ = "est_entradas_nf"

    id = Column(Integer, primary_key=True, index=True)
    numero_nf = Column(String(50), nullable=False)
    fornecedor = Column(String(200), nullable=False)
    data_entrada = Column(Date, nullable=False)
    familia_id = Column(Integer, nullable=True)
    observacoes = Column(Text)
    conferido_por = Column(Integer, nullable=True)  # user id, sem FK
    created_at = Column(DateTime, default=datetime.utcnow)

class EntradaNFItem(Base):
    """Itens de uma entrada de NF"""
    __tablename__ = "est_entradas_nf_itens"

    id = Column(Integer, primary_key=True, index=True)
    entrada_nf_id = Column(Integer, nullable=False)
    item_id = Column(Integer, nullable=False)
    lote_id = Column(Integer, nullable=True)    # lote gerado
    quantidade = Column(Float, nullable=False)
    lote_codigo = Column(String(100))           # código do lote informado
    validade = Column(Date, nullable=True)
    observacoes = Column(Text)

# ─── MOVIMENTAÇÃO DE ESTOQUE ──────────────────────────────────────────────────

class TipoMovimento(str, enum.Enum):
    ENTRADA_NF = "ENTRADA_NF"           # entrada por nota fiscal
    PRODUCAO_PI = "PRODUCAO_PI"         # produção de PI (consome MP)
    PRODUCAO_PA = "PRODUCAO_PA"         # produção de PA (consome PI + EMB)
    SAIDA_MANUAL = "SAIDA_MANUAL"       # saída avulsa
    ENTRADA_MANUAL = "ENTRADA_MANUAL"   # entrada avulsa (ajuste)
    AJUSTE = "AJUSTE"                   # ajuste de inventário

class Movimentacao(Base):
    """Log completo de todas as movimentações de estoque"""
    __tablename__ = "est_movimentacoes"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(30), nullable=False)
    item_id = Column(Integer, nullable=False)
    lote_id = Column(Integer, nullable=True)
    familia_id = Column(Integer, nullable=True)
    quantidade = Column(Float, nullable=False)   # positivo=entrada, negativo=saída
    saldo_apos = Column(Float, nullable=False)   # saldo total do item após movimento
    referencia_id = Column(Integer, nullable=True)    # id do lançamento de produção ou NF
    referencia_tipo = Column(String(50), nullable=True)  # "producao" / "entrada_nf"
    observacoes = Column(Text)
    usuario_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ─── LANÇAMENTO DE PRODUÇÃO ───────────────────────────────────────────────────

class LancamentoProducao(Base):
    """Registro de produção: PI produzido ou PA produzido"""
    __tablename__ = "est_lancamentos_producao"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, nullable=False)       # PI ou PA produzido
    familia_id = Column(Integer, nullable=True)
    quantidade = Column(Float, nullable=False)
    lote_gerado_id = Column(Integer, nullable=True) # lote criado para o item produzido
    data_producao = Column(Date, nullable=False)
    turno = Column(String(20))                      # Turno 1 / Turno 2 / etc.
    observacoes = Column(Text)
    usuario_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class LancamentoProducaoConsumo(Base):
    """Consumo de cada componente em um lançamento de produção"""
    __tablename__ = "est_lancamentos_consumo"

    id = Column(Integer, primary_key=True, index=True)
    lancamento_id = Column(Integer, nullable=False)
    item_id = Column(Integer, nullable=False)       # MP, EMB ou PI consumido
    lote_id = Column(Integer, nullable=True)        # lote específico consumido
    quantidade = Column(Float, nullable=False)
    observacoes = Column(Text)
