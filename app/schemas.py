from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

# User Schemas
class UserBase(BaseModel):
    name: str
    email: str
    role: str = "ADMIN"
    store: Optional[str] = None
    active: bool = True

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Customer Schemas
class CustomerBase(BaseModel):
    name: str
    external_key: str
    cpf_cnpj: Optional[str] = None
    whatsapp: Optional[str] = None
    store: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    profile_cobranca: str = "AUTOMATICO"

class CustomerUpdate(BaseModel):
    whatsapp: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    profile_cobranca: Optional[str] = None
    email: Optional[str] = None
    perfil_devedor: Optional[str] = None

class Customer(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Installment Schemas
class InstallmentBase(BaseModel):
    contract_id: str
    installment_number: int
    issue_date: Optional[date] = None
    due_date: date
    amount: Decimal
    open_amount: Decimal
    status: str = "ABERTA"

class Installment(InstallmentBase):
    id: int
    customer_id: int
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Collection Action Schemas
class CollectionActionBase(BaseModel):
    action_type: str
    outcome: str
    notes: Optional[str] = None
    promised_date: Optional[date] = None
    promised_amount: Optional[Decimal] = None

class CollectionActionCreate(CollectionActionBase):
    customer_id: int
    user_id: Optional[int] = None  # Preenchido pelo backend via sessão
    installment_id: Optional[int] = None

class CollectionAction(CollectionActionBase):
    id: int
    customer_id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# API Response Schemas
class PriorityQueueItem(BaseModel):
    cliente_id: int
    nome_cliente: str
    phone: str
    valor_em_aberto: float
    max_atraso: int
    data_vencimento: str
    profile_cobranca: str
    ultimo_contato_str: str
    ultimo_outcome: Optional[str] = None
    qtd_parcelas: int
    status_label: str
    regua_nivel: str
    perfil_devedor: Optional[str] = None
    score_propensao: Optional[int] = None
    pausado_ate: Optional[str] = None  # 'YYYY-MM-DD' quando cobrança pausada

class QueueStats(BaseModel):
    total_carteira: int
    sem_contato_hoje: int
    promessas_abertas: int

class PriorityQueueResponse(BaseModel):
    items: List[PriorityQueueItem]
    total_items: int
    total_pages: int
    current_page: int
    stats: Optional[QueueStats] = None
