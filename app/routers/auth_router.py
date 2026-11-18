import secrets
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    require_admin,
    verify_password,
)
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentification & Invitations"])


def generate_secure_invite_code(prefix: str = "INV-TUN") -> str:
    """Génère un code d'invitation unique et lisible."""
    chars = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(8))
    return f"{prefix}-{random_part}"


@router.post(
    "/invite",
    response_model=schemas.InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer un code d'invitation (Réservé Admin)",
    description="Permet à un administrateur d'émettre un code d'invitation rattaché à un établissement hospitalier pour un médecin ou un interne.",
)
def create_invitation(
    invite_in: schemas.InvitationCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    # Vérification de l'existence de l'établissement (Tenant)
    tenant = db.query(models.Tenant).filter(models.Tenant.id == invite_in.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Établissement (Tenant ID: {invite_in.tenant_id}) introuvable.",
        )

    # Génération d'un code unique
    for _ in range(10):
        code = generate_secure_invite_code()
        exists = db.query(models.Invitation).filter(models.Invitation.code == code).first()
        if not exists:
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de générer un code d'invitation unique.",
        )

    expires_at = datetime.now(timezone.utc) + timedelta(days=invite_in.expires_in_days)

    invitation = models.Invitation(
        code=code,
        email=invite_in.email.lower() if invite_in.email else None,
        role=invite_in.role,
        tenant_id=invite_in.tenant_id,
        is_used=False,
        expires_at=expires_at,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


@router.post(
    "/register-with-invite",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription praticien via code d'invitation",
    description="Permet l'enregistrement d'un médecin ou interne avec validation du code d'invitation et contrôle du numéro CNOM.",
)
def register_with_invite(
    register_in: schemas.RegisterWithInviteRequest,
    db: Session = Depends(get_db),
):
    # 1. Vérification de la validité de l'invitation
    invitation = (
        db.query(models.Invitation)
        .filter(models.Invitation.code == register_in.invite_code.strip())
        .first()
    )

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Code d'invitation introuvable ou invalide.",
        )

    if invitation.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce code d'invitation a déjà été utilisé.",
        )

    # Vérification d'expiration avec fuseau horaire UTC
    now_utc = datetime.now(timezone.utc)
    invitation_expires = invitation.expires_at
    if invitation_expires.tzinfo is None:
        invitation_expires = invitation_expires.replace(tzinfo=timezone.utc)

    if invitation_expires < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce code d'invitation est expiré.",
        )

    # Si l'invitation était assignée à un email précis
    if invitation.email and invitation.email.lower() != register_in.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ce code d'invitation est réservé à l'adresse email '{invitation.email}'.",
        )

    # 2. Vérification unicité email
    existing_user_email = (
        db.query(models.User).filter(models.User.email == register_in.email.lower()).first()
    )
    if existing_user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un compte utilisateur avec cette adresse email existe déjà.",
        )

    # 3. Validation spécifique au corps médical tunisien (CNOM)
    if invitation.role == models.UserRole.MEDECIN.value:
        if not register_in.cnom_number or not register_in.cnom_number.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le numéro CNOM (Conseil National de l'Ordre des Médecins) est obligatoire pour les médecins.",
            )

    if register_in.cnom_number:
        clean_cnom = register_in.cnom_number.strip().upper()
        existing_user_cnom = (
            db.query(models.User).filter(models.User.cnom_number == clean_cnom).first()
        )
        if existing_user_cnom:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le numéro CNOM '{clean_cnom}' est déjà rattaché à un autre praticien.",
            )
    else:
        clean_cnom = None

    # 4. Création de l'utilisateur
    new_user = models.User(
        email=register_in.email.lower(),
        hashed_password=get_password_hash(register_in.password),
        full_name=register_in.full_name.strip(),
        cnom_number=clean_cnom,
        role=invitation.role,
        tenant_id=invitation.tenant_id,
        is_active=True,
    )

    # 5. Marquage de l'invitation comme consommée
    invitation.is_used = True

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Connexion praticien / administrateur (OAuth2)",
    description="Compatible directement avec le bouton 'Authorize' de Swagger UI. Utilise username (email) et password.",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # Dans OAuth2PasswordRequestForm, l'identifiant est transmis dans le champ 'username'
    user = (
        db.query(models.User)
        .filter(models.User.email == form_data.username.strip().lower())
        .first()
    )

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides (email ou mot de passe incorrect).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte utilisateur est inactif. Veuillez contacter votre chef de service.",
        )

    access_token = create_access_token(
        data={
            "sub": user.email,
            "id": user.id,
            "role": user.role,
            "tenant_id": user.tenant_id,
        }
    )

    return schemas.Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        full_name=user.full_name,
    )


@router.get(
    "/me",
    response_model=schemas.UserResponse,
    summary="Profil de l'utilisateur connecté",
    description="Retourne les informations du profil médical actuellement authentifié.",
)
def get_current_user_profile(
    current_user: models.User = Depends(get_current_user),
):
    return current_user
