export type StatutOffre = "brouillon" | "modifiee" | "validee" | "refusee" | "envoyee";

export interface LigneOffre {
  reference: string;
  designation: string;
  conditionnement: number;
  alliage: string;
  quantite_boites: number;
  prix_unitaire_ht: number;
  remise_pct: number;
  prix_total_ht: number;
  en_stock: boolean;
  delai_livraison: string;
  score_similarite: number;
  description_originale_client: string;
}

export interface Offre {
  id: string;
  numero_offre: string;
  statut: StatutOffre;
  montant_ht: number;
  montant_tva: number;
  montant_ttc: number;
  texte_intro: string;
  texte_conclusion: string;
  lignes: LigneOffre[];
  created_at: string;
  validee_le?: string;
  tokens_utilises?: number;
  cout_usd?: number;
  latence_ms?: number;
  langfuse_trace_id?: string;
  expediteur_nom: string;
  expediteur_email: string;
  sujet: string;
  corps_email: string;
  recu_le: string;
  nb_lignes: number;
}

export interface OffreUpdatePayload {
  lignes: LigneOffre[];
  montant_ht: number;
  montant_tva: number;
  montant_ttc: number;
  texte_intro: string;
  texte_conclusion: string;
  statut: StatutOffre;
}

export const STATUT_CONFIG: Record<
  StatutOffre,
  { label: string; color: string }
> = {
  brouillon: {
    label: "Brouillon IA",
    color: "bg-amber-100 text-amber-800 border border-amber-200",
  },
  modifiee: {
    label: "Modifiée",
    color: "bg-blue-100 text-blue-800 border border-blue-200",
  },
  validee: {
    label: "Validée",
    color: "bg-green-100 text-green-800 border border-green-200",
  },
  refusee: {
    label: "Refusée",
    color: "bg-red-100 text-red-800 border border-red-200",
  },
  envoyee: {
    label: "Envoyée",
    color: "bg-purple-100 text-purple-800 border border-purple-200",
  },
};

export function formatEur(amount: number) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format(amount);
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
