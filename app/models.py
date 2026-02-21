from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Boolean,
    ForeignKey, Numeric, Text, Index
)
from sqlalchemy.orm import relationship
from .core.database import Base

def today():
    return datetime.utcnow().date()

def days_overdue(due: date) -> int:
    return (today() - due).days

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(190), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="ADMIN")  # ADMIN/COBRANCA
    store = Column(String(80), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    external_key = Column(String(190), unique=True, nullable=False)
    name = Column(String(190), nullable=False)
    cpf_cnpj = Column(String(40), nullable=True)
    whatsapp = Column(String(40), nullable=True)
    store = Column(String(80), nullable=True)
    address = Column(String(255), nullable=True)
    email = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    profile_cobranca = Column(String(20), nullable=False, default="AUTOMATICO")
    msgs_ativo = Column(Boolean, default=True, server_default="1")
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    assigned_to = relationship("User")
    installments = relationship("Installment", back_populates="customer", cascade="all, delete-orphan")
    actions = relationship("CollectionAction", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_customers_name', 'name'),
        Index('ix_customers_store', 'store'),
        Index('ix_customers_assigned_to', 'assigned_to_user_id'),
    )

class Installment(Base):
    __tablename__ = "installments"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    contract_id = Column(String(120), nullable=False)
    installment_number = Column(Integer, nullable=False, default=1)
    issue_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=False)
    amount = Column(Numeric(12,2), nullable=False)
    open_amount = Column(Numeric(12,2), nullable=False)
    status = Column(String(20), nullable=False, default="ABERTA")
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="installments")

class CollectionAction(Base):
    __tablename__ = "collection_actions"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    installment_id = Column(Integer, ForeignKey("installments.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(20), nullable=False)
    outcome = Column(String(120), nullable=False)
    notes = Column(Text, nullable=True)
    promised_date = Column(Date, nullable=True)
    promised_amount = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="actions")
    user = relationship("User")

class CollectionRule(Base):
    __tablename__ = "collection_rules"
    id = Column(Integer, primary_key=True)
    level = Column(String(20), nullable=False, default="LEVE")  # LEVE, MODERADA, INTENSA
    start_days = Column(Integer, nullable=False)
    end_days = Column(Integer, nullable=False)
    default_action = Column(String(20), nullable=False, default="WHATSAPP")
    template_message = Column(Text, nullable=False, default="")
    frequency = Column(Integer, nullable=False, default=1)
    priority = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, default=True)

class SentMessage(Base):
    __tablename__ = "sent_messages"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rule_id = Column(Integer, ForeignKey("collection_rules.id"), nullable=True)
    channel = Column(String(20), nullable=False)  # WHATSAPP, CALL, EMAIL
    template_used = Column(Text, nullable=True)
    message_body = Column(Text, nullable=True)
    phone = Column(String(40), nullable=True)
    status = Column(String(20), nullable=False, default="SIMULADO")  # SIMULADO, PENDENTE, ENVIADO, FALHA
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer")
    user = relationship("User")
    rule = relationship("CollectionRule")

class ComissaoCobranca(Base):
    __tablename__ = "comissoes_cobranca"
    id = Column(Integer, primary_key=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    store = Column(String(80), nullable=True)
    portfolio_range = Column(String(20), nullable=False) # 30, 60, 90
    total_receivable = Column(Numeric(12, 2), nullable=False)
    recovery_goal = Column(Numeric(12, 2), nullable=False)
    actual_recovered = Column(Numeric(12, 2), nullable=False)
    achieved_percent = Column(Numeric(12, 2), nullable=False)
    commission_percent = Column(Numeric(5, 2), nullable=False)
    commission_value = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

class Configuracoes(Base):
    __tablename__ = "configuracoes"
    id = Column(Integer, primary_key=True)
    whatsapp_ativo = Column(Boolean, default=False)
    whatsapp_modo_teste = Column(Boolean, default=True)
    whatsapp_instancia = Column(String(100), nullable=True)
    whatsapp_token = Column(String(100), nullable=True)
    whatsapp_client_token = Column(String(100), nullable=True)
    scheduler_hora_disparo = Column(Integer, default=9, server_default="9")
    director_alert_min_installments = Column(Integer, default=3, server_default="3")
    updated_at = Column(DateTime, default=datetime.utcnow)

class WhatsappHistorico(Base):
    __tablename__ = "whatsapp_historico"
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    telefone = Column(String(20), nullable=True)
    mensagem = Column(Text, nullable=True)
    tipo = Column(String(50), nullable=True)  # 'regua_automatica', 'manual', 'lembrete'
    status = Column(String(20), nullable=True) # 'enviado', 'simulado', 'erro'
    resposta = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    cliente = relationship("Customer")

class MessageDispatchLog(Base):
    __tablename__ = "message_dispatch_log"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    scheduled_for = Column(Date, nullable=True) # quando deveria enviar
    executed_at = Column(DateTime, default=datetime.utcnow)
    mode = Column(String(20)) # TEST/PROD
    status = Column(String(20)) # SIMULATED, SENT, FAILED, RESCHEDULED, SKIPPED
    regua = Column(String(20)) # LEVE, MODERADA, INTENSA
    gatilho_dias = Column(Integer)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(190))
    destination_phone = Column(String(40))
    cpf_mask = Column(String(20))
    
    # Detalhes financeiros snapshot
    data_vencimento = Column(Date, nullable=True)
    valor_original = Column(Numeric(10, 2), nullable=True)
    valor_atualizado = Column(Numeric(10, 2), nullable=True)
    total_divida = Column(Numeric(10, 2), nullable=True)
    qtd_parcelas_atrasadas = Column(Integer, nullable=True)
    
    compliance_block_reason = Column(String(50), nullable=True) # DOMINGO | FERIADO_NACIONAL | FORA_HORARIO_COMERCIAL | OK
    message_rendered = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True) # JSON string
    
    customer = relationship("Customer")

    __table_args__ = (
        Index('ix_mdl_scheduled', 'scheduled_for'),
        Index('ix_mdl_status_created', 'status', 'created_at'),
        Index('ix_mdl_customer_created', 'customer_id', 'created_at'),
        Index('ix_mdl_regua_gatilho', 'regua', 'gatilho_dias', 'created_at'),
    )

class Director(Base):
    __tablename__ = "directors"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40), nullable=False) # WhatsApp format
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DirectorAlertLog(Base):
    __tablename__ = "director_alert_logs"
    id = Column(Integer, primary_key=True)
    director_id = Column(Integer, ForeignKey("directors.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    alert_date = Column(Date, default=today)
    created_at = Column(DateTime, default=datetime.utcnow)

    director = relationship("Director")
    customer = relationship("Customer")

class FinancialUser(Base):
    __tablename__ = "financial_users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class FinancialAlertLog(Base):
    __tablename__ = "financial_alert_logs"
    id = Column(Integer, primary_key=True)
    financial_user_id = Column(Integer, ForeignKey("financial_users.id"), nullable=False)
    alert_date = Column(Date, default=today)
    item_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    financial_user = relationship("FinancialUser")

class ReconciliationStats(Base):
    __tablename__ = "reconciliation_stats"
    id = Column(Integer, primary_key=True)
    date = Column(Date, default=today, unique=True)
    total_paid_erp = Column(Integer, default=0)
    normally_paid = Column(Integer, default=0)
    cancelled_or_deleted = Column(Integer, default=0)
    details_json = Column(Text, nullable=True)  # Lista de Docs cancelados/divergentes
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ConferenciaTitulos(Base):
    __tablename__ = "conferencia_titulos"
    id = Column(Integer, primary_key=True)
    data_processamento = Column(DateTime, default=datetime.utcnow)
    resumo_json = Column(Text, nullable=False) # Totais de cada tipo
    detalhes_json = Column(Text, nullable=False) # Lista completa de títulos e situações
    created_at = Column(DateTime, default=datetime.utcnow)
