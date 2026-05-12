from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime

# ─── AUTH ─────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class ChangePassword(BaseModel):
    senha_atual: str
    nova_senha: str

# ─── USER ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    nome: str
    email: str
    password: str
    role: str = "tecnico"
    cargo: Optional[str] = None
    telefone: Optional[str] = None
    matricula: Optional[str] = None

class UserUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    cargo: Optional[str] = None
    telefone: Optional[str] = None
    matricula: Optional[str] = None
    is_active: Optional[bool] = None

class UserOut(BaseModel):
    id: int
    nome: str
    email: str
    role: str
    cargo: Optional[str]
    telefone: Optional[str]
    matricula: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ─── FAMÍLIA ──────────────────────────────────────────────────────────────────

class FamiliaCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None
    cor: Optional[str] = "#3B82F6"

class FamiliaUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    cor: Optional[str] = None
    is_active: Optional[bool] = None

class FamiliaOut(BaseModel):
    id: int
    nome: str
    descricao: Optional[str]
    cor: str
    is_active: bool

    class Config:
        from_attributes = True

# ─── RECEITA ──────────────────────────────────────────────────────────────────

class ReceitaItemCreate(BaseModel):
    item_filho_id: int
    quantidade: float
    unidade: Optional[str] = None
    observacoes: Optional[str] = None

class ReceitaItemOut(BaseModel):
    id: int
    item_filho_id: int
    quantidade: float
    unidade: Optional[str]
    observacoes: Optional[str]
    item_filho_nome: Optional[str] = None
    item_filho_codigo: Optional[str] = None
    item_filho_tipo: Optional[str] = None
    item_filho_unidade: Optional[str] = None

    class Config:
        from_attributes = True

# ─── ITEM ─────────────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    codigo: str
    nome: str
    tipo: str  # MP / EMB / PI / PA
    unidade: str = "Kg"
    familia_id: Optional[int] = None
    estoque_minimo: float = 0.0
    observacoes: Optional[str] = None
    receita: Optional[List[ReceitaItemCreate]] = None

class ItemUpdate(BaseModel):
    codigo: Optional[str] = None
    nome: Optional[str] = None
    unidade: Optional[str] = None
    familia_id: Optional[int] = None
    estoque_minimo: Optional[float] = None
    observacoes: Optional[str] = None
    is_active: Optional[bool] = None
    receita: Optional[List[ReceitaItemCreate]] = None

class ItemOut(BaseModel):
    id: int
    codigo: str
    nome: str
    tipo: str
    unidade: str
    familia_id: Optional[int]
    familia_nome: Optional[str] = None
    familia_cor: Optional[str] = None
    estoque_minimo: float
    estoque_atual: float = 0.0
    status_estoque: str = "OK"
    observacoes: Optional[str]
    is_active: bool
    receita: Optional[List[ReceitaItemOut]] = None

    class Config:
        from_attributes = True

# ─── LOTE ─────────────────────────────────────────────────────────────────────

class LoteOut(BaseModel):
    id: int
    codigo_lote: str
    item_id: int
    item_nome: Optional[str] = None
    item_codigo: Optional[str] = None
    familia_id: Optional[int]
    familia_nome: Optional[str] = None
    quantidade_inicial: float
    quantidade_atual: float
    data_entrada: date
    validade: Optional[date]
    is_active: bool

    class Config:
        from_attributes = True

# ─── ENTRADA NF ───────────────────────────────────────────────────────────────

class EntradaNFItemCreate(BaseModel):
    item_id: int
    quantidade: float
    lote_codigo: Optional[str] = None
    validade: Optional[date] = None
    observacoes: Optional[str] = None

class EntradaNFCreate(BaseModel):
    numero_nf: str
    fornecedor: str
    data_entrada: date
    familia_id: Optional[int] = None
    observacoes: Optional[str] = None
    itens: List[EntradaNFItemCreate]

class EntradaNFItemOut(BaseModel):
    id: int
    item_id: int
    item_nome: Optional[str] = None
    item_codigo: Optional[str] = None
    quantidade: float
    lote_codigo: Optional[str]
    lote_id: Optional[int]
    validade: Optional[date]
    observacoes: Optional[str]

    class Config:
        from_attributes = True

class EntradaNFOut(BaseModel):
    id: int
    numero_nf: str
    fornecedor: str
    data_entrada: date
    familia_id: Optional[int]
    familia_nome: Optional[str] = None
    observacoes: Optional[str]
    itens: Optional[List[EntradaNFItemOut]] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ─── PRODUÇÃO ─────────────────────────────────────────────────────────────────

class ConsumoManualItem(BaseModel):
    item_id: int
    lote_id: Optional[int] = None  # None = FIFO automático
    quantidade: float

class LancamentoProducaoCreate(BaseModel):
    item_id: int          # PI ou PA a produzir
    familia_id: Optional[int] = None
    quantidade: float
    data_producao: date
    turno: Optional[str] = None
    observacoes: Optional[str] = None
    lote_codigo: Optional[str] = None  # lote do item produzido
    consumo_manual: Optional[List[ConsumoManualItem]] = None  # override do consumo automático

class ConsumoPreviewItem(BaseModel):
    item_id: int
    item_nome: str
    item_codigo: str
    item_tipo: str
    quantidade_necessaria: float
    unidade: str
    estoque_atual: float
    saldo_apos: float
    suficiente: bool
    lotes_disponiveis: List[dict] = []

class LancamentoProducaoPreview(BaseModel):
    item_id: int
    item_nome: str
    item_tipo: str
    quantidade: float
    consumo: List[ConsumoPreviewItem]
    pode_produzir: bool

class LancamentoProducaoOut(BaseModel):
    id: int
    item_id: int
    item_nome: Optional[str] = None
    familia_id: Optional[int]
    familia_nome: Optional[str] = None
    quantidade: float
    lote_gerado_id: Optional[int]
    data_producao: date
    turno: Optional[str]
    observacoes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# ─── MOVIMENTAÇÃO ─────────────────────────────────────────────────────────────

class MovimentacaoOut(BaseModel):
    id: int
    tipo: str
    item_id: int
    item_nome: Optional[str] = None
    item_codigo: Optional[str] = None
    lote_id: Optional[int]
    lote_codigo: Optional[str] = None
    familia_id: Optional[int]
    familia_nome: Optional[str] = None
    quantidade: float
    saldo_apos: float
    observacoes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_mp: int
    total_emb: int
    total_pi: int
    total_pa: int
    itens_estoque_baixo: int
    entradas_mes: int
    producoes_mes: int
    movimentacoes_hoje: int
