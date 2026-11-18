import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.auth import get_password_hash
from app.config import settings
from app.database import SessionLocal, init_database
from app.routers import auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("traumato-api")


def seed_demo_data() -> None:
    """Insère les données initiales de démonstration si la base est vide."""
    db = SessionLocal()
    try:
        # 1. Vérification ou création du Tenant de démonstration
        tenant = (
            db.query(models.Tenant)
            .filter(models.Tenant.name == "Service Traumatologie - Hôpital Régional de Bizerte")
            .first()
        )
        if not tenant:
            tenant = models.Tenant(
                name="Service Traumatologie - Hôpital Régional de Bizerte",
                region="Bizerte",
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            logger.info("Données démo : Tenant '%s' créé avec succès.", tenant.name)

        # 2. Vérification ou création de l'Admin
        admin_email = "admin@traumato.tn"
        admin = db.query(models.User).filter(models.User.email == admin_email).first()
        if not admin:
            admin = models.User(
                email=admin_email,
                hashed_password=get_password_hash("Admin2026!"),
                full_name="Dr. Administrateur Système",
                cnom_number=None,
                role=models.UserRole.ADMIN.value,
                tenant_id=tenant.id,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Données démo : Administrateur '%s' créé (Mot de passe: Admin2026!).", admin_email)

        # 3. Vérification ou création du Médecin
        doctor_email = "dr.amine@traumato.tn"
        doctor = db.query(models.User).filter(models.User.email == doctor_email).first()
        if not doctor:
            doctor = models.User(
                email=doctor_email,
                hashed_password=get_password_hash("Medecin2026!"),
                full_name="Dr. Amine Ben Salem",
                cnom_number="TN-14582",
                role=models.UserRole.MEDECIN.value,
                tenant_id=tenant.id,
                is_active=True,
            )
            db.add(doctor)
            db.commit()
            logger.info(
                "Données démo : Médecin '%s' créé (CNOM: TN-14582, Mot de passe: Medecin2026!).",
                doctor_email,
            )

        # 4. Vérification ou création du code d'invitation actif
        invite_code = "INVITE-TUN-2026"
        invitation = (
            db.query(models.Invitation)
            .filter(models.Invitation.code == invite_code)
            .first()
        )
        if not invitation:
            invitation = models.Invitation(
                code=invite_code,
                email=None,
                role=models.UserRole.MEDECIN.value,
                tenant_id=tenant.id,
                is_used=False,
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
            db.add(invitation)
            db.commit()
            logger.info(
                "Données démo : Code d'invitation actif '%s' généré pour 1 an.",
                invite_code,
            )

    except Exception as e:
        db.rollback()
        logger.error("Erreur lors de l'insertion des données de démonstration: %s", e)
        raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cycle de vie FastAPI : initialisation de la BD, pgvector et données de démonstration."""
    logger.info("Démarrage du service Traumatologie Backend...")
    init_database()
    seed_demo_data()
    logger.info("Application prête à recevoir les requêtes.")
    yield
    logger.info("Arrêt du service Traumatologie Backend.")


app = FastAPI(
    title="TraumatoTN - Système Médical Traumatologie (FR/AR)",
    description=(
        "Backend de l'application médicale bilingue (Français / Arabe) en traumatologie.\n\n"
        "### Étape 1 : Infrastructure & Authentification Médicale par Invitation\n"
        "- Base de données PostgreSQL avec extension vectorielle **pgvector**.\n"
        "- Gestion multi-tenant (Établissements hospitaliers tunisiens).\n"
        "- Inscription sécurisée par code d'invitation avec validation du numéro **CNOM**.\n"
        "- Authentification JWT standard avec support OAuth2 Swagger (/docs).\n\n"
        "### Comptes de démonstration pré-configurés :\n"
        "- **Admin** : `admin@traumato.tn` / `Admin2026!`\n"
        "- **Médecin** : `dr.amine@traumato.tn` / `Medecin2026!` (CNOM: `TN-14582`)\n"
        "- **Code d'invitation actif** : `INVITE-TUN-2026`"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routeurs
app.include_router(auth_router.router)


@app.get("/", tags=["Santé du Système"])
def root():
    """Point d'entrée principal avec diagnostic rapide et lien vers la documentation."""
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "demo_accounts": {
            "admin": "admin@traumato.tn",
            "medecin": "dr.amine@traumato.tn",
            "active_invite_code": "INVITE-TUN-2026",
        },
    }


@app.get("/health", tags=["Santé du Système"])
def health_check():
    """Vérification de l'état de l'API."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
