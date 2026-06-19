import type { Offre, LigneOffre } from "./types";

/** Données de démo alignées sur articles_industriels_1000.xlsx et la maquette DOCX. */

const MAIL_DUPONT = `Bonjour,

Nous souhaitons recevoir un devis pour les pièces suivantes :

- 5 boîtes de vis hexagonales M10x30 inox
- 10 boîtes d'écrous M12 acier zingué
- 2 boîtes de rondelles M16 inox 316

Merci de nous faire parvenir votre meilleure offre.

Cordialement,
Jean Dupont
Atelier Dupont SAS`;

function ligne(
  reference: string,
  designation: string,
  conditionnement: number,
  alliage: string,
  quantite_boites: number,
  prix_unitaire_ht: number,
  en_stock: boolean,
  delai_livraison: string,
  score_similarite: number,
  description_originale_client: string,
  remise_pct = 0
): LigneOffre {
  const prix_total_ht = parseFloat(
    (quantite_boites * prix_unitaire_ht * (1 - remise_pct / 100)).toFixed(2)
  );
  return {
    reference,
    designation,
    conditionnement,
    alliage,
    quantite_boites,
    prix_unitaire_ht,
    remise_pct,
    prix_total_ht,
    en_stock,
    delai_livraison,
    score_similarite,
    description_originale_client,
  };
}

function buildOffre(
  partial: Omit<Offre, "montant_ht" | "montant_tva" | "montant_ttc" | "nb_lignes">
): Offre {
  const montant_ht = parseFloat(
    partial.lignes.reduce((sum, l) => sum + l.prix_total_ht, 0).toFixed(2)
  );
  const montant_tva = parseFloat((montant_ht * 0.2).toFixed(2));
  const montant_ttc = parseFloat((montant_ht + montant_tva).toFixed(2));
  return {
    ...partial,
    montant_ht,
    montant_tva,
    montant_ttc,
    nb_lignes: partial.lignes.length,
  };
}

const now = new Date().toISOString();
const yesterday = new Date(Date.now() - 86400000).toISOString();
const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();

export const DEMO_OFFRES: Offre[] = [
  buildOffre({
    id: "demo-0042",
    numero_offre: "OP-2026-0042",
    statut: "brouillon",
    texte_intro:
      "Madame, Monsieur Dupont,\n\nNous avons bien pris note de votre demande et avons le plaisir de vous adresser notre offre de prix pour les fournitures industrielles listées ci-dessous.",
    texte_conclusion:
      "Cette offre est valable 30 jours. Les articles en stock sont expédiables sous 1 semaine. Conditions de paiement : 30 jours fin de mois. Franco de port pour toute commande supérieure à 500 € HT.",
    lignes: [
      ligne(
        "959310YH",
        "Rondelle plate M24",
        50,
        "Inox A4",
        5,
        40.0,
        true,
        "1 semaine",
        0.91,
        "5 boîtes de vis hexagonales M10x30 inox"
      ),
      ligne(
        "511615MW",
        "Écrou hexagonal M20",
        10,
        "Acier zingué",
        10,
        12.28,
        true,
        "1 semaine",
        0.88,
        "10 boîtes d'écrous M12 acier zingué"
      ),
      ligne(
        "908386HR",
        "Boulon hexagonal M30x10",
        500,
        "Inox 316",
        2,
        39.6,
        true,
        "1 semaine",
        0.86,
        "2 boîtes de rondelles M16 inox 316"
      ),
    ],
    created_at: now,
    tokens_utilises: 1847,
    cout_usd: 0.0011,
    latence_ms: 2340,
    langfuse_trace_id: "demo-trace-0042",
    expediteur_nom: "Atelier Dupont SAS",
    expediteur_email: "j.dupont@atelier-dupont.fr",
    sujet: "Demande de prix – pièces inox",
    corps_email: MAIL_DUPONT,
    recu_le: now,
  }),
  buildOffre({
    id: "demo-0041",
    numero_offre: "OP-2026-0041",
    statut: "brouillon",
    texte_intro: "Madame, Monsieur,\n\nVeuillez trouver ci-joint notre proposition commerciale.",
    texte_conclusion: "Offre valable 30 jours. Délais indicatifs selon disponibilité stock.",
    lignes: [
      ligne(
        "104332DY",
        "Vis à tête hexagonale M16x100",
        5,
        "Acier",
        8,
        7.25,
        true,
        "1 semaine",
        0.92,
        "8 boîtes vis M16 acier"
      ),
      ligne(
        "525534ZY",
        "Rondelle Grower M20",
        25,
        "Acier traité",
        4,
        273.76,
        false,
        "3 mois",
        0.79,
        "4 boîtes rondelles Grower M20"
      ),
    ],
    created_at: yesterday,
    tokens_utilises: 1520,
    cout_usd: 0.0009,
    latence_ms: 1980,
    expediteur_nom: "Chaudronnerie Morin",
    expediteur_email: "achats@chaudronnerie-morin.fr",
    sujet: "Consultation boulonnerie",
    corps_email: "Bonjour,\nMerci de nous chiffrer 8 boîtes de vis M16 acier et 4 boîtes de rondelles Grower M20.\nCordialement",
    recu_le: yesterday,
  }),
  buildOffre({
    id: "demo-0040",
    numero_offre: "OP-2026-0040",
    statut: "modifiee",
    texte_intro: "Bonjour,\n\nSuite à votre demande, veuici notre offre révisée.",
    texte_conclusion: "Remise accordée sur la ligne Inox A4. Validité 30 jours.",
    lignes: [
      ligne(
        "511615MW",
        "Écrou hexagonal M20",
        10,
        "Acier zingué",
        15,
        12.28,
        true,
        "1 semaine",
        0.9,
        "15 boîtes écrous M20 zingués",
        5
      ),
    ],
    created_at: weekAgo,
    expediteur_nom: "Méca Provençale",
    expediteur_email: "contact@meca-provencale.fr",
    sujet: "Re: devis écrous",
    corps_email: "Pouvez-vous nous proposer 15 boîtes d'écrous M20 zingués ?",
    recu_le: weekAgo,
  }),
  buildOffre({
    id: "demo-0039",
    numero_offre: "OP-2026-0039",
    statut: "validee",
    texte_intro: "Madame, Monsieur,\n\nOffre validée par notre équipe commerciale.",
    texte_conclusion: "Merci pour votre confiance.",
    lignes: [
      ligne(
        "959310YH",
        "Rondelle plate M24",
        50,
        "Inox A4",
        3,
        124.8,
        true,
        "1 semaine",
        0.94,
        "3 boîtes rondelles M24 inox A4"
      ),
    ],
    created_at: weekAgo,
    expediteur_nom: "BTP Auvergne",
    expediteur_email: "appro@btp-auvergne.fr",
    sujet: "Commande rondelles",
    corps_email: "Devis pour 3 boîtes rondelles M24 inox A4 svp.",
    recu_le: weekAgo,
  }),
  buildOffre({
    id: "demo-0038",
    numero_offre: "OP-2026-0038",
    statut: "envoyee",
    texte_intro: "Bonjour,\n\nVeuillez trouver l'offre transmise par email.",
    texte_conclusion: "Offre envoyée au client le 12/06/2026.",
    lignes: [
      ligne(
        "104332DY",
        "Vis à tête hexagonale M16x100",
        5,
        "Acier",
        20,
        7.25,
        true,
        "1 semaine",
        0.93,
        "20 boîtes vis M16x100"
      ),
    ],
    created_at: weekAgo,
    expediteur_nom: "Indus Normandie",
    expediteur_email: "achats@indus-normandie.fr",
    sujet: "Vis M16 - urgent",
    corps_email: "Besoin de 20 boîtes de vis M16x100 acier.",
    recu_le: weekAgo,
  }),
];

let demoStore: Offre[] = DEMO_OFFRES.map((o) => structuredClone(o));

export function getDemoOffres(statut?: string): Offre[] {
  if (!statut || statut === "tous") return structuredClone(demoStore);
  return structuredClone(demoStore.filter((o) => o.statut === statut));
}

export function getDemoOffre(id: string): Offre | undefined {
  const found = demoStore.find((o) => o.id === id);
  return found ? structuredClone(found) : undefined;
}

export function updateDemoOffre(id: string, payload: Partial<Offre>): void {
  demoStore = demoStore.map((o) =>
    o.id === id ? structuredClone({ ...o, ...payload }) : o
  );
}

export function removeDemoOffreSelection(id: string, statut: Offre["statut"]): void {
  updateDemoOffre(id, { statut });
}

export function useDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_USE_DEMO !== "false";
}
