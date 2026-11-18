import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEDECIN = "medecin"
    INTERNE = "interne"


class DocumentLanguage(str, enum.Enum):
    FR = "fr"
    AR = "ar"


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class Tenant(Base):
    """Établissement ou service hospitalier (multi-tenant)."""

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    region = Column(String(100), nullable=False)

    users = relationship("User", back_populates="tenant")
    invitations = relationship("Invitation", back_populates="tenant")
    documents = relationship("Document", back_populates="tenant")


class User(Base):
    """Utilisateurs du système médical (administrateurs, médecins, internes)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    cnom_number = Column(String(50), unique=True, index=True, nullable=True)
    role = Column(String(20), default=UserRole.MEDECIN.value, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", back_populates="users")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")


class Invitation(Base):
    """Code d'invitation sécurisé pour l'enregistrement des praticiens."""

    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(20), default=UserRole.MEDECIN.value, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    tenant = relationship("Tenant", back_populates="invitations")


class Document(Base):
    """Référence documentaire médicale (protocoles, guides traumatologie)."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    language = Column(String(10), nullable=False)  # "fr" ou "ar"
    file_path = Column(String(500), nullable=False)
    is_validated = Column(Boolean, default=False, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tenant = relationship("Tenant", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Segments de documents découpés pour le RAG avec vecteur d'embedding 1024D."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, default=1, nullable=False)
    content = Column(Text, nullable=False)
    # Embedding 1024 dimensions (e.g., bge-large-en/ar/fr ou multilingual-e5)
    embedding = Column(Vector(1024), nullable=True)

    document = relationship("Document", back_populates="chunks")


class Conversation(Base):
    """Session de consultation ou discussion clinique d'un praticien."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), default="Nouvelle consultation", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Message d'une conversation (requête praticien ou réponse assistant médical)."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" ou "assistant"
    content = Column(Text, nullable=False)
    citations_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    reports = relationship("Report", back_populates="message", cascade="all, delete-orphan")


class Report(Base):
    """Signalement d'erreur clinique, d'incohérence ou d'hallucination sur un message."""

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), default=ReportStatus.OPEN.value, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="reports")
    message = relationship("Message", back_populates="reports")
