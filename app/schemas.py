from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, ConfigDict, Field


# -----------------------------------------------------------------------------
# Tenant Schemas
# -----------------------------------------------------------------------------
class TenantBase(BaseModel):
    name: str = Field(..., example="Service Traumatologie - Hôpital Régional de Bizerte")
    region: str = Field(..., example="Bizerte")


class TenantCreate(TenantBase):
    pass


class TenantResponse(TenantBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# User Schemas
# -----------------------------------------------------------------------------
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    cnom_number: Optional[str] = None
    role: Literal["admin", "medecin", "interne"] = "medecin"
    tenant_id: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    cnom_number: Optional[str] = None
    role: str
    tenant_id: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Invitation Schemas
# -----------------------------------------------------------------------------
class InvitationCreate(BaseModel):
    email: Optional[EmailStr] = Field(
        None,
        description="Email cible pré-assigné pour l'invitation (optionnel)",
        example="nouveau.medecin@traumato.tn",
    )
    role: Literal["admin", "medecin", "interne"] = Field(
        "medecin",
        description="Rôle attribué via ce code d'invitation",
    )
    tenant_id: int = Field(
        ...,
        description="Identifiant de l'établissement hospitalier",
        example=1,
    )
    expires_in_days: int = Field(
        7,
        ge=1,
        le=90,
        description="Durée de validité du code d'invitation en jours",
    )


class InvitationResponse(BaseModel):
    id: int
    code: str
    email: Optional[str] = None
    role: str
    tenant_id: int
    is_used: bool
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegisterWithInviteRequest(BaseModel):
    invite_code: str = Field(
        ...,
        description="Code d'invitation fourni par l'administrateur",
        example="INVITE-TUN-2026",
    )
    email: EmailStr = Field(..., example="dr.nour@traumato.tn")
    password: str = Field(..., min_length=8, example="Secret2026!")
    full_name: str = Field(..., example="Dr. Nour Chérif")
    cnom_number: Optional[str] = Field(
        None,
        description="Numéro d'inscription au Conseil National de l'Ordre des Médecins de Tunisie",
        example="TN-18945",
    )


# -----------------------------------------------------------------------------
# Token & Auth Schemas
# -----------------------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    exp: Optional[int] = None
