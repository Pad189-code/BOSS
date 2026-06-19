from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractedPart(BaseModel):
    description: str = Field(description="Libellé ou référence demandée par le client")
    quantity: int = Field(ge=1, default=1)


class QuoteLineItem(BaseModel):
    """Ligne d'offre alignée sur le catalogue Excel et la maquette DOCX."""

    client_description: str
    catalog_sku: str
    catalog_name: str
    quantity: int = Field(ge=1, description="Nombre de boîtes commandées")
    unit_price: float = Field(ge=0, description="Prix boîte HT en EUR")
    line_total: float = Field(ge=0)
    similarity_score: float | None = None
    conditionnement: int | None = Field(default=None, description="Pièces par boîte")
    alliage: str | None = None
    remise_pct: float = Field(default=0, ge=0, le=100)
    en_stock: bool = True
    delai_livraison: str | None = None


class QuoteOffer(BaseModel):
    client_name: str | None = None
    greeting: str = Field(description="Texte d'introduction de l'offre")
    lines: list[QuoteLineItem]
    subtotal: float = Field(ge=0)
    tax_rate: float = Field(default=0.20, ge=0, le=1)
    tax_amount: float = Field(ge=0)
    total_amount: float = Field(ge=0)
    currency: str = "EUR"
    closing_notes: str = Field(description="Texte de conclusion et conditions")


class QuoteLineItemDashboard(BaseModel):
    """Format dashboard employé (aligné maquette 1440x665)."""

    reference: str
    designation: str
    conditionnement: int
    alliage: str
    quantite_boites: int
    prix_unitaire_ht: float
    remise_pct: float = 0
    prix_total_ht: float
    en_stock: bool
    delai_livraison: str
    score_similarite: float | None = None
    description_originale_client: str


class OffreSummary(BaseModel):
    id: UUID
    numero_offre: str
    statut: str
    montant_ht: float
    montant_tva: float
    montant_ttc: float
    expediteur_nom: str
    expediteur_email: str
    sujet: str
    created_at: datetime
    recu_le: datetime
    nb_lignes: int


class OffreDetail(OffreSummary):
    texte_intro: str
    texte_conclusion: str
    corps_email: str
    lignes: list[QuoteLineItemDashboard]
    tokens_utilises: int | None = None
    cout_usd: float | None = None
    latence_ms: int | None = None
    langfuse_trace_id: str | None = None


class OffreDocxPayload(BaseModel):
    """Données nécessaires à la génération DOCX (compatible mode démo)."""

    numero_offre: str
    expediteur_nom: str
    expediteur_email: str
    sujet: str
    created_at: datetime | str
    texte_intro: str = ""
    texte_conclusion: str = ""
    montant_ht: float
    montant_tva: float
    montant_ttc: float
    lignes: list[QuoteLineItemDashboard]


class OffreUpdateRequest(BaseModel):
    lignes: list[QuoteLineItemDashboard] | None = None
    montant_ht: float | None = None
    montant_tva: float | None = None
    montant_ttc: float | None = None
    texte_intro: str | None = None
    texte_conclusion: str | None = None
    statut: str | None = None


class QuoteValidationUpdate(BaseModel):
    cover_letter: str | None = None
    texte_intro: str | None = None
    texte_conclusion: str | None = None
    lines: list[QuoteLineItem] | None = None


class QuoteDetailResponse(BaseModel):
    id: UUID
    email_request_id: UUID
    status: str
    client_name: str | None
    cover_letter: str | None
    total_amount: float
    currency: str
    lines: list[QuoteLineItem]
    email_subject: str | None
    email_body: str
    from_address: str
